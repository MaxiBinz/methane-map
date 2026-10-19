#!/usr/bin/env python3
"""Audit frozen component evidence without changing categories or raw inputs.

Run after a complete baseline: .venv/bin/python scripts/audit_candidates.py
This checks evidence contracts, catalog associations, geometry and contextual
diagnostics. It does not perform a radiance fit, wind reconstruction, surface
reflectance analysis or independent-sensor confirmation. Heuristic flags never
automatically reject a component or establish a new source.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import numpy as np
from pyproj import Transformer
from rasterio.features import geometry_mask
from rasterio.transform import Affine
from shapely import transform
from shapely.geometry import MultiPoint, Point, box, shape

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from methane_hunter.nasa_catalog import load_nasa_catalog, match_nasa_catalog
from methane_hunter.quality import quality_mask_for_enhancement


PROJECT = Transformer.from_crs(4326, 32613, always_xy=True)
UNPERFORMED = [
    "independent radiance/spectral retrieval verification",
    "surface-reflectance and mineral-confounding comparison",
    "independent wind field and plume-direction consistency",
    "independent satellite or ground observation",
    "facility identification and attribution",
    "emission-rate estimation",
]
REQUIRED_FILES = ("enhancement", "sensitivity", "uncertainty", "quality")


def read(root, relative):
    return json.loads((root / relative).read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project(geometry):
    return transform(geometry, lambda coordinates: np.column_stack(
        PROJECT.transform(coordinates[:, 0], coordinates[:, 1])))


def utc(value):
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("Timezone-aware observation timestamps are required")
    return timestamp.astimezone(timezone.utc)


def difference(a, b):
    return abs((utc(a) - utc(b)).total_seconds())


def approximate(a, b, *, absolute=1e-5, relative=1e-8):
    return (isinstance(a, (int, float)) and isinstance(b, (int, float))
            and math.isclose(a, b, abs_tol=absolute, rel_tol=relative))


def connected_groups(ids, pairs):
    """Return contextual neighbor groups, not verified duplicate emissions."""
    neighbors = {identifier: set() for identifier in ids}
    for pair in pairs:
        a, b = pair["candidate_ids"]
        neighbors[a].add(b)
        neighbors[b].add(a)
    remaining = set(ids)
    groups = []
    while remaining:
        start = min(remaining)
        found, queue = set(), [start]
        while queue:
            node = queue.pop()
            if node in found:
                continue
            found.add(node)
            queue.extend(neighbors[node] - found)
        remaining -= found
        if len(found) > 1:
            groups.append(sorted(found))
    return sorted(groups)


def source_context(geometry, candidate, catalog, distance_limit=1000):
    references = []
    for source in catalog:
        distance = geometry.distance(project(Point(source["geometry_json"]["coordinates"])))
        if distance > distance_limit:
            continue
        delta = difference(candidate["observed_at"], source["scene_timestamp"])
        references.append({
            "catalog_id": source["plume_id"], "catalog_record_id": source["id"],
            "source_point": source["geometry_json"]["coordinates"],
            "observed_at": source["scene_timestamp"],
            "point_to_component_distance_m": float(distance),
            "time_difference_seconds": delta,
            "same_acquisition_time_window": delta <= 120,
            "different_calendar_date": utc(candidate["observed_at"]).date() != utc(source["scene_timestamp"]).date(),
            "interpretation": "finite-catalog spatial context; not independent confirmation or source attribution",
        })
    return sorted(references, key=lambda record: (
        not record["same_acquisition_time_window"], record["point_to_component_distance_m"], record["catalog_id"]))


def quality_neighborhoods(root, candidates, by_scene, projected):
    """Re-read five-flag masks; measure context to excluded pixel centers.

    This is not a residual-cloud classifier. The nearest unavailable/flagged
    pixel may represent water, a cloud dilation, another selected flag, or GLT
    missing support. Distance is measured from the component polygon in UTM13
    to pixel centers, so it is approximate at half-pixel boundary scale.
    """
    diagnostics = {}
    for scene_id in sorted({candidate["scene_id"] for candidate in candidates}):
        files = by_scene[scene_id]["files"]
        usable, info = quality_mask_for_enhancement(root / files["quality"]["path"],
                                                  root / files["enhancement"]["path"])
        if info["crs"] != "EPSG:4326":
            raise ValueError("Quality-neighborhood audit expects the EMIT WGS84 grid")
        grid = Affine(*info["target_transform"])
        for candidate in (record for record in candidates if record["scene_id"] == scene_id):
            r0, c0, r1, c1 = candidate["bbox_rc"]
            component_window = usable[r0:r1, c0:c1]
            local_grid = grid * Affine.translation(c0, r0)
            support = geometry_mask([candidate["geometry"]], out_shape=component_window.shape,
                                    transform=local_grid, invert=True)
            # The native ~50x60m grid needs fewer than 35 pixels per 1.5km;
            # forty pixels supplies a conservative context window.
            y0, x0 = max(0, r0 - 40), max(0, c0 - 40)
            y1, x1 = min(usable.shape[0], r1 + 40), min(usable.shape[1], c1 + 40)
            yy, xx = np.where(~usable[y0:y1, x0:x1])
            nearest = None
            if len(yy):
                longitude, latitude = grid * (xx + x0 + .5, yy + y0 + .5)
                easting, northing = PROJECT.transform(longitude, latitude)
                distance = projected[candidate["candidate_id"]].distance(MultiPoint(np.column_stack((easting, northing))))
                if distance <= 1500:
                    nearest = float(distance)
            diagnostics[candidate["candidate_id"]] = {
                "excluded_component_pixels": int(np.count_nonzero(support & ~component_window)),
                "component_pixels_checked": int(support.sum()),
                "nearest_excluded_quality_pixel_center_distance_m_within_1500m": nearest,
                "quality_mask_sha256_recomputed": info["mask_sha256"],
                "proximity_definition": "UTM13 component polygon to nearest five-flag/GLT-excluded pixel center; approximate at half-pixel scale",
                "limitation": "Proximity alone does not establish contamination or identify which quality flag caused exclusion.",
            }
        del usable
    return diagnostics


def audit(root):
    tracked = [
        "outputs/run_summary.json", "outputs/run_parameters.json", "outputs/candidates.json",
        "data/nasa_input_manifest.json", "data/metadata/nasa_selection.json",
        "data/metadata/carbonmapper_scene_plumes.json",
        "data/metadata/carbonmapper_regional_plumes.json",
        "data/metadata/nasa_plume_cmr_same_scenes.json", "data/nasa_download_ledger.json",
    ]
    input_hashes = {path: digest(root / path) for path in tracked}
    summary = read(root, "outputs/run_summary.json")
    params = read(root, "outputs/run_parameters.json")
    manifest = read(root, "data/nasa_input_manifest.json")
    selection = read(root, "data/metadata/nasa_selection.json")
    if (summary.get("provisional") is not False or summary.get("scenes_analyzed") != 20
            or params.get("provisional_limit") is not None or len(manifest) != 20):
        raise ValueError("Audit requires a completed, nonprovisional twenty-scene baseline")
    candidates = read(root, "outputs/candidates.json")
    scene_catalog = read(root, "data/metadata/carbonmapper_scene_plumes.json")
    regional_catalog = read(root, "data/metadata/carbonmapper_regional_plumes.json")
    nasa_catalog = load_nasa_catalog(root / "data/metadata/nasa_plume_cmr_same_scenes.json")
    if scene_catalog.get("pagination_complete") is not True:
        raise ValueError("Per-scene Carbon Mapper catalog pagination must be complete")
    carbon_mapper = scene_catalog["items"]
    historical = {record["id"]: record for record in regional_catalog["response"]["items"]}
    historical.update({record["id"]: record for record in carbon_mapper})
    historical = list(historical.values())
    ledger = [record for record in read(root, "data/nasa_download_ledger.json") if record.get("status") == "ok"]
    successful = {record["path"]: record for record in ledger}
    by_scene = {record["scene"]["name"]: record for record in manifest}
    selected = {record["name"]: record for record in selection["scenes"]}
    roi = box(*selection["bbox"])
    root_errors = []
    if input_hashes["data/nasa_input_manifest.json"] != params.get("input_manifest_sha256"):
        root_errors.append("input manifest hash differs from the completed analysis")
    if input_hashes["data/metadata/nasa_selection.json"] != params.get("selection_sha256"):
        root_errors.append("selection hash differs from the completed analysis")
    if len(candidates) != summary.get("screened_components"):
        root_errors.append("candidate count differs from run summary")
    if len({candidate["candidate_id"] for candidate in candidates}) != len(candidates):
        root_errors.append("candidate IDs are not unique")

    geometries = {candidate["candidate_id"]: shape(candidate["geometry"]) for candidate in candidates}
    projected = {identifier: project(geometry) for identifier, geometry in geometries.items()}
    quality_context = quality_neighborhoods(root, candidates, by_scene, projected)
    duplicate_pairs, recurrence_pairs = [], []
    for i, first in enumerate(candidates):
        for second in candidates[i + 1:]:
            a, b = first["candidate_id"], second["candidate_id"]
            distance = projected[a].distance(projected[b])
            delta = difference(first["observed_at"], second["observed_at"])
            if delta <= 120 and distance <= 300:
                duplicate_pairs.append({
                    "candidate_ids": [a, b], "geometry_distance_m": float(distance),
                    "time_difference_seconds": delta,
                    "cross_granule": first["scene_id"] != second["scene_id"],
                    "geometry_overlap_area_m2": float(projected[a].intersection(projected[b]).area),
                    "interpretation": "possible same-event fragmentation or duplicate; no automatic merging",
                })
            if utc(first["observed_at"]).date() != utc(second["observed_at"]).date() and distance <= 1000:
                recurrence_pairs.append({
                    "candidate_ids": [a, b], "geometry_distance_m": float(distance),
                    "time_difference_seconds": delta,
                    "interpretation": "recurring spatial neighborhood; shared source or persistent artifact remains unproven",
                })
    groups = connected_groups(list(geometries), duplicate_pairs)
    grouped = {identifier: f"potential-event-group-{i:02d}"
               for i, members in enumerate(groups, start=1) for identifier in members}
    audits = []
    for candidate in candidates:
        identifier = candidate["candidate_id"]
        geometry, metric = geometries[identifier], projected[identifier]
        errors = []
        scene = by_scene.get(candidate["scene_id"])
        if scene is None or candidate["scene_id"] not in selected:
            raise ValueError(f"Candidate {identifier} refers to an unknown selected scene")
        scene = scene["scene"]
        if candidate["role"] != selected[candidate["scene_id"]]["role"]:
            errors.append("candidate role differs from frozen selection")
        if difference(candidate["observed_at"], scene["timestamp"]) != 0:
            errors.append("candidate timestamp differs from source scene")
        if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in ("Polygon", "MultiPolygon"):
            errors.append("candidate geometry is empty, invalid, or nonpolygonal")
        inside = roi.covers(geometry)
        outside_area = project(geometry.difference(roi)).area if not inside else 0.0
        if not inside:
            errors.append("candidate polygon extends outside the fixed analysis region")
        if not approximate(candidate["longitude"], geometry.centroid.x, absolute=1e-10):
            errors.append("longitude does not represent the recorded enhancement centroid")
        if not approximate(candidate["latitude"], geometry.centroid.y, absolute=1e-10):
            errors.append("latitude does not represent the recorded enhancement centroid")
        if not approximate(candidate["area_m2"], metric.area):
            errors.append("candidate area differs from UTM13 geometry area")

        checked_files = []
        for kind in REQUIRED_FILES:
            record = candidate["source_files"].get(kind)
            expected = by_scene[candidate["scene_id"]]["files"].get(kind)
            if record != expected or not isinstance(record, dict):
                errors.append(f"{kind} provenance differs from input manifest")
                continue
            path = root / record["path"]
            success = successful.get(record["path"])
            if (not path.is_file() or path.stat().st_size != record.get("bytes")
                    or not re.fullmatch(r"[0-9a-f]{64}", record.get("sha256", ""))):
                errors.append(f"{kind} file missing, size changed, or invalid SHA-256 metadata")
            if not success or success.get("sha256") != record.get("sha256") or success.get("url") != record.get("url"):
                errors.append(f"{kind} does not agree with successful acquisition ledger")
            filename_timestamp = re.search(r"_(\d{8}T\d{6})_", path.name)
            if not filename_timestamp or filename_timestamp.group(1) != utc(candidate["observed_at"]).strftime("%Y%m%dT%H%M%S"):
                errors.append(f"{kind} filename acquisition time differs from candidate")
            checked_files.append({"kind": kind, "path": record["path"], "sha256": record["sha256"],
                                  "bytes": record["bytes"], "raw_rehash_in_this_audit": kind == "quality"})
        quality = read(root, f"outputs/quality/{candidate['scene_id']}.json")
        if quality.get("mask_sha256") != candidate["source_files"]["quality"]["sha256"]:
            errors.append("quality-grid diagnostic refers to another source mask hash")
        if "no resampling" not in quality.get("mapping", "") or len(quality.get("selected_flags", [])) != 5:
            errors.append("quality-grid alignment or selected binary flags lack required evidence")
        pixel_quality = quality_context[identifier]
        if pixel_quality["excluded_component_pixels"]:
            errors.append("candidate includes a pixel excluded by the recomputed five-flag quality mask")
        if pixel_quality["component_pixels_checked"] != candidate["pixel_count"]:
            errors.append("candidate polygon support disagrees with its reported pixel count")
        if pixel_quality["quality_mask_sha256_recomputed"] != candidate["source_files"]["quality"]["sha256"]:
            errors.append("quality mask raw SHA-256 changed during the independent context check")

        context = source_context(metric, candidate, historical)
        expected_cm = {record["catalog_id"]: record for record in source_context(
            metric, candidate, carbon_mapper, params["catalog_distance_m"])}
        actual_cm = {record["catalog_id"]: record for record in candidate.get("catalog_matches", [])}
        if set(expected_cm) != set(actual_cm):
            errors.append("stored Carbon Mapper associations differ from recomputed point-to-polygon search")
        for key in set(expected_cm) & set(actual_cm):
            expected_association = ("same_acquisition_neighborhood" if expected_cm[key]["time_difference_seconds"]
                                    <= params["catalog_time_seconds"] else "spatial_other_date")
            if (actual_cm[key]["association"] != expected_association
                    or not approximate(actual_cm[key]["point_to_component_distance_m"], expected_cm[key]["point_to_component_distance_m"])
                    or actual_cm[key]["time_difference_seconds"] != expected_cm[key]["time_difference_seconds"]):
                errors.append(f"Carbon Mapper association details disagree for {key}")
        expected_nasa = {record.catalog_id: record.to_dict() for record in match_nasa_catalog(
            geometry, candidate["observed_at"], nasa_catalog,
            time_tolerance_seconds=params["catalog_time_seconds"])}
        actual_nasa = {record["catalog_id"]: record for record in candidate.get("nasa_plume_outline_matches", [])}
        if set(expected_nasa) != set(actual_nasa):
            errors.append("stored NASA precise-outline associations differ from recomputed overlap")
        for key in set(expected_nasa) & set(actual_nasa):
            if (not approximate(actual_nasa[key]["candidate_overlap_fraction"], expected_nasa[key]["candidate_overlap_fraction"], absolute=1e-10)
                    or not approximate(actual_nasa[key]["overlap_area_m2"], expected_nasa[key]["overlap_area_m2"])
                    or actual_nasa[key].get("independent_corroboration") is not False):
                errors.append(f"NASA association details disagree for {key}")
        same_cm = [record for record in actual_cm.values() if record["association"] == "same_acquisition_neighborhood"]
        expected_category = "E" if same_cm or expected_nasa else "C"
        if candidate.get("category") not in ("C", "E") or candidate["category"] != expected_category:
            errors.append("initial category is inconsistent with finite-catalog association rule")
        if (candidate.get("facility") is not None or candidate.get("possible_source") is not None
                or candidate.get("emission_rate_kg_h") is not None
                or candidate.get("independent_sensor_corroboration") is not False):
            errors.append("candidate includes unsupported source, facility, rate, or corroboration claim")
        if any("annual" in key.lower() and value is not None for key, value in candidate.items()):
            errors.append("candidate contains an unsupported annual-emission field")

        flags = set(candidate.get("flags", []))
        annulus_count = candidate.get("local_annulus_pixels", 0)
        contrast = candidate.get("local_annulus_contrast_sigma")
        annulus_missing = contrast is None or annulus_count < 32
        annulus_weak = contrast is not None and contrast < 3
        if annulus_missing and "insufficient_local_annulus" not in flags:
            errors.append("missing local-annulus information is not flagged")
        if annulus_weak and "weak_local_annulus_contrast" not in flags:
            errors.append("weak local-annulus contrast is not flagged")
        if contrast is not None:
            calculated = ((candidate["median_ppm_m"] - candidate["local_annulus_median_ppm_m"])
                          / max(candidate["local_annulus_robust_sigma_ppm_m"], 1))
            if not approximate(contrast, calculated):
                errors.append("local-annulus contrast does not agree with recorded inputs")
        if candidate["sensitivity_median"] < .3 and "large_sensitivity_correction" not in flags:
            errors.append("large sensitivity correction is not flagged")

        same_neighborhood = [record for record in context if record["same_acquisition_time_window"]]
        wider_same = [record for record in same_neighborhood
                      if record["point_to_component_distance_m"] > params["catalog_distance_m"]]
        other_dates = [record for record in context if record["different_calendar_date"]]
        if wider_same:
            flags.add("same_acquisition_catalog_source_between_300m_and_1km")
        if other_dates:
            flags.add("other_date_catalog_source_within_1km")
        if identifier in grouped:
            flags.add("possible_same_event_fragmentation_or_duplicate")
        recurrence = [pair for pair in recurrence_pairs if identifier in pair["candidate_ids"]]
        if recurrence:
            flags.add("other_date_component_neighborhood_within_1km")
        if pixel_quality["nearest_excluded_quality_pixel_center_distance_m_within_1500m"] is not None:
            flags.add("quality_excluded_pixel_neighborhood_within_1_5km")
        if expected_nasa and max(record["candidate_overlap_fraction"] for record in expected_nasa.values()) < .5:
            flags.add("published_outline_covers_less_than_half_the_component")
        nearest_same = []
        for reference in carbon_mapper:
            if difference(candidate["observed_at"], reference["scene_timestamp"]) <= 120:
                nearest_same.append({"catalog_id": reference["plume_id"], "source_point": reference["geometry_json"]["coordinates"],
                                     "point_to_component_distance_m": float(metric.distance(project(Point(reference["geometry_json"]["coordinates"]))))})
        nearest_same.sort(key=lambda record: (record["point_to_component_distance_m"], record["catalog_id"]))
        score = (10 if candidate["category"] == "C" else 0) + len(flags) + 100 * bool(errors)
        priority = "high" if candidate["category"] == "C" or errors else "medium" if flags else "low"
        audits.append({
            "candidate_id": identifier, "scene_id": candidate["scene_id"],
            "observed_at": candidate["observed_at"], "scene_role": candidate["role"],
            "initial_category": candidate["category"], "category_after_audit": candidate["category"],
            "audit_reclassification": False, "novelty_established": False,
            "independent_corroboration": False,
            "review_priority": priority, "review_priority_score": score,
            "contract_checks_passed": not errors, "contract_errors": errors,
            "geometry_within_roi": inside, "outside_roi_area_m2": float(outside_area),
            "area_m2": float(metric.area), "source_files_checked": checked_files,
            "carbon_mapper_same_acquisition_matches": same_cm,
            "nasa_precise_outline_matches": list(expected_nasa.values()),
            "same_acquisition_catalog_context_within_1km": same_neighborhood,
            "other_date_catalog_context_within_1km": other_dates,
            "nearest_same_acquisition_catalog_source": nearest_same[0] if nearest_same else None,
            "potential_same_event_group": grouped.get(identifier),
            "spatial_recurrence_pairs": recurrence,
            "local_annulus": {"pixel_count": annulus_count, "contrast_sigma": contrast,
                               "missing_or_insufficient": annulus_missing, "weak_contrast": annulus_weak,
                               "interpretation": "robust spatial diagnostic, not a calibrated probability"},
            "sensitivity_median": candidate["sensitivity_median"],
            "sensor_uncertainty_median_ppm_m": candidate["sensor_uncertainty_median_ppm_m"],
            "quality_exclusion_context": pixel_quality,
            "review_flags": sorted(flags),
            "review_flag_notes": (["The baseline boundary flag retains its original wording. Per-scene catalog context now includes source points outside the ROI; the flag indicates proximity, not a proven missing-reference gap."]
                                  if "near_region_boundary_catalog_outside_roi_not_excluded" in flags else []),
            "checked": ["frozen selection and acquisition timestamp", "manifest/ledger hash metadata and actual file size",
                        "candidate geometry, ROI and centroid", "recomputed CM point and NASA precise-outline associations",
                        "recomputed five-flag GLT quality support and exclusion-neighborhood context", "local-annulus and sensitivity diagnostics",
                        "component-neighbor and other-date catalog context", "absence of facility and rate claims"],
            "unchecked": UNPERFORMED,
            "alternative_explanations": list(dict.fromkeys(candidate.get("alternative_explanations", []) + [
                "physical plume enhancement requiring independent spectral confirmation",
                "fragment or tail of a previously cataloged emission outside the 300m association tolerance",
                "surface/mineral spectral interference or persistent background structure",
                "residual contamination near a quality-excluded region",
            ])),
            "evidence_assessment": ("Published same-EMIT observation association; no independent atmospheric confirmation."
                                    if candidate["category"] == "E" else
                                    "Ambiguous enhancement component. Wider source context may explain a catalog-neighborhood miss; novelty is not established."),
        })
    for relative, original in input_hashes.items():
        if digest(root / relative) != original:
            raise ValueError(f"Input changed during candidate audit: {relative}")
    by_category = Counter(record["initial_category"] for record in audits)
    by_role = Counter(record["scene_role"] for record in audits)
    by_flags = Counter(flag for record in audits for flag in record["review_flags"])
    audit_errors = root_errors + [f"{record['candidate_id']}: {error}" for record in audits for error in record["contract_errors"]]
    result = {
        "created_at": datetime.now(timezone.utc).isoformat(), "audit_version": "candidate_adversarial_audit_v1",
        "input_sha256": input_hashes,
        "scope": "All components from the completed frozen 20-scene baseline; no additional downloads or automatic category changes",
        "thresholds": {"catalog_association_m": params["catalog_distance_m"], "same_acquisition_seconds": 120,
                       "potential_duplicate_geometry_distance_m": 300, "recurrence_and_catalog_context_m": 1000},
        "provenance_limit": ("Primary analysis verified all raw SHA-256 values. This audit checks hash metadata and file sizes for candidate inputs, and rehashes only the "
                             f"{len({candidate['scene_id'] for candidate in candidates})} distinct quality masks read for component-neighborhood checks."),
        "context_catalog_scope": {"selected_scene_ch4_records": len(carbon_mapper),
                                  "regional_plus_selected_scene_historical_records": len(historical),
                                  "nasa_precise_plume_polygons": len(nasa_catalog),
                                  "independent_observing_sensor": False},
        "summary": {
            "components_audited": len(audits), "by_initial_category": dict(by_category),
            "by_scene_role": dict(by_role), "by_review_flag": dict(by_flags),
            "all_contract_checks_passed": not audit_errors, "contract_errors": audit_errors,
            "all_component_geometries_within_roi": all(record["geometry_within_roi"] for record in audits),
            "potential_same_event_pairs": len(duplicate_pairs), "potential_same_event_groups": len(groups),
            "cross_granule_potential_duplicate_pairs": sum(pair["cross_granule"] for pair in duplicate_pairs),
            "other_date_component_neighborhood_pairs": len(recurrence_pairs),
            "components_with_other_date_catalog_context_within_1km": sum(bool(record["other_date_catalog_context_within_1km"]) for record in audits),
            "category_C_with_same_acquisition_catalog_context_within_1km": sum(record["initial_category"] == "C" and bool(record["same_acquisition_catalog_context_within_1km"]) for record in audits),
            "components_with_missing_or_weak_annulus": sum(record["local_annulus"]["missing_or_insufficient"] or record["local_annulus"]["weak_contrast"] for record in audits),
            "components_near_quality_exclusion_within_1500m": sum(record["quality_exclusion_context"]["nearest_excluded_quality_pixel_center_distance_m_within_1500m"] is not None for record in audits),
            "components_with_excluded_quality_pixels": sum(record["quality_exclusion_context"]["excluded_component_pixels"] > 0 for record in audits),
            "components_reclassified_or_rejected": 0, "novelty_established": False,
            "independent_physical_validation_performed": False,
            "review_priority_order": [record["candidate_id"] for record in sorted(audits, key=lambda record: (-record["review_priority_score"], record["candidate_id"]))],
        },
        "potential_same_event_pairs": duplicate_pairs,
        "potential_same_event_groups": [{"group_id": f"potential-event-group-{i:02d}", "candidate_ids": group,
                                         "interpretation": "neighboring components; no verified source/event count implied"}
                                        for i, group in enumerate(groups, start=1)],
        "other_date_component_neighborhood_pairs": recurrence_pairs,
        "candidates": audits,
        "unchecked_for_every_component": UNPERFORMED,
        "limitations": ["Nearby same-event components may be plume fragments, separate sources, or common artifacts.",
                        "Catalog context outside 300m is an alternative explanation, not an automatic match.",
                        "Cross-date spatial recurrence can indicate a recurring source or persistent surface artifact.",
                        "Category E describes a catalog association; Category C does not establish novelty.",
                        "No heuristic flag alone assigns Category D or confirms a methane plume."],
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    result = audit(root)
    output = root / "outputs/adversarial_audit.json"
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    fields = ["candidate_id", "scene_id", "observed_at", "scene_role", "initial_category", "category_after_audit",
              "review_priority", "contract_checks_passed", "geometry_within_roi", "outside_roi_area_m2",
              "potential_same_event_group", "nearest_same_acquisition_source_distance_m", "same_acquisition_sources_within_1km",
              "other_date_sources_within_1km", "annulus_contrast_sigma", "sensitivity_median",
              "quality_exclusion_nearest_pixel_center_distance_m_within_1500m", "review_flags",
              "novelty_established", "independent_corroboration", "unchecked"]
    with (root / "outputs/adversarial_audit.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in result["candidates"]:
            row = {field: record.get(field) for field in fields}
            nearest = record["nearest_same_acquisition_catalog_source"]
            row.update({"nearest_same_acquisition_source_distance_m": nearest["point_to_component_distance_m"] if nearest else None,
                        "same_acquisition_sources_within_1km": len(record["same_acquisition_catalog_context_within_1km"]),
                        "other_date_sources_within_1km": len(record["other_date_catalog_context_within_1km"]),
                        "annulus_contrast_sigma": record["local_annulus"]["contrast_sigma"],
                        "quality_exclusion_nearest_pixel_center_distance_m_within_1500m": record["quality_exclusion_context"]["nearest_excluded_quality_pixel_center_distance_m_within_1500m"],
                        "review_flags": "; ".join(record["review_flags"]), "unchecked": "; ".join(record["unchecked"])})
            writer.writerow(row)
    print(json.dumps(result["summary"], indent=2))
    return 0 if result["summary"]["all_contract_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
