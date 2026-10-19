"""Frozen, CPU-only EMIT analysis with explicit evidence and validation outputs.

The screen generates enhancement hypotheses. No function estimates a facility's
emissions or turns catalog absence into novelty. All coordinates of hypotheses
refer to enhancement geometry, not to an identified source.
"""
from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime
import gc
import json
import os
from pathlib import Path
import tempfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "methane-hunter-matplotlib"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import numpy as np
import pandas as pd
from pyproj import Transformer
from rasterio.features import geometry_mask, shapes
from rasterio.transform import Affine, xy
from rasterio.warp import transform_geom
from scipy import ndimage
from shapely.geometry import box, mapping, shape, Point
from shapely.ops import transform as project, unary_union

from .data import aligned_rasters, sha256, utc_now, write_json
from .detection import DetectionConfig, screen_enhancements
from .quality import quality_mask_for_enhancement
from .nasa_catalog import load_nasa_catalog, match_nasa_catalog

METHOD = "EMIT V002 sensitivity-corrected enhancement; local robust background and sensor-noise screen"
MERCATOR = Transformer.from_crs("EPSG:4326", "EPSG:32613", always_xy=True).transform


def _delta(a, b):
    return abs((datetime.fromisoformat(a.replace("Z", "+00:00")) -
                datetime.fromisoformat(b.replace("Z", "+00:00"))).total_seconds())


def _catalog(root):
    per_scene = root / "data/metadata/carbonmapper_scene_plumes.json"
    if per_scene.exists():
        return [r for r in json.loads(per_scene.read_text())["items"] if r["gas"] == "CH4"]
    snapshot = json.loads((root / "data/metadata/carbonmapper_regional_plumes.json").read_text())
    return [r for r in snapshot["response"]["items"] if r["gas"] == "CH4"]


def component_geometry(labels, label, transform, crs):
    mask = labels == label
    geoms = [shape(g) for g, v in shapes(mask.astype("uint8"), mask=mask, transform=transform) if v == 1]
    merged = unary_union(geoms)
    if str(crs) != "EPSG:4326":
        merged = shape(transform_geom(crs, "EPSG:4326", mapping(merged)))
    return merged


def polygon_catalog_matches(geometry, timestamp, catalog, tolerance_m=300, time_seconds=120):
    """Associate a source point with enhancement support, without attribution.

    Polygon distance avoids an arbitrary plume-tail centroid offset. Matching
    the same EMIT acquisition is not independent corroboration.
    """
    metric = project(MERCATOR, geometry)
    matches = []
    for r in catalog:
        coords = r["geometry_json"]["coordinates"]
        distance = metric.distance(project(MERCATOR, Point(*coords)))
        if distance > tolerance_m:
            continue
        delta = _delta(timestamp, r["scene_timestamp"])
        matches.append({"catalog_id": r["plume_id"], "catalog_record_id": r["id"],
                        "source_point": coords, "point_to_component_distance_m": float(distance),
                        "time_difference_seconds": delta,
                        "association": "same_acquisition_neighborhood" if delta <= time_seconds else "spatial_other_date",
                        "source_url": "https://data.carbonmapper.org/"})
    return sorted(matches, key=lambda x: (x["association"] != "same_acquisition_neighborhood", x["point_to_component_distance_m"]))


def _plot_scene(root, index, scene, meta, result, rows, catalog):
    t = Affine(*meta["transform"])
    height, width = result.corrected.shape
    bounds = [t.c, t.c + width * t.a, t.f + height * t.e, t.f]
    fig, ax = plt.subplots(figsize=(9, 7), layout="constrained")
    cm = plt.get_cmap("magma").copy()
    cm.set_bad("#e9e9e9")
    im = ax.imshow(result.corrected, extent=bounds, origin="upper", cmap=cm,
                   norm=Normalize(0, 3000), interpolation="nearest")
    region = json.loads((root / "investigation.json").read_text())["bbox"]
    ax.set_xlim(max(bounds[0], region[0]), min(bounds[1], region[2]))
    ax.set_ylim(max(bounds[2], region[1]), min(bounds[3], region[3]))
    for r in catalog:
        if _delta(scene["timestamp"], r["scene_timestamp"]) <= 120:
            lon, lat = r["geometry_json"]["coordinates"]
            ax.scatter(lon, lat, marker="x", s=30, color="#16a6c1", linewidths=1)
    for r in rows:
        ax.scatter(r["longitude"], r["latitude"], s=50, facecolors="none",
                   edgecolors="#1d9cc3" if r["category"] == "E" else "#4aa840", linewidths=1.2)
    ax.set_aspect(1 / np.cos(np.deg2rad(32)))
    ax.set_xlabel("Longitude (WGS84)")
    ax.set_ylabel("Latitude (WGS84)")
    ax.set_title(f"{index:02d} · {scene['timestamp']} · {scene['role']}\n{len(rows)} screened components; grey = unavailable or quality excluded", fontsize=11)
    fig.colorbar(im, ax=ax, label="Sensitivity-corrected methane enhancement (ppm m)", shrink=.8, extend="max")
    path = root / "outputs/maps" / f"scene_{index:02d}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return str(path.relative_to(root))


def run_analysis(root=".", *, limit=None):
    root = Path(root)
    manifest_path = root / "data/nasa_input_manifest.json"
    records = json.loads(manifest_path.read_text())
    selection = json.loads((root / "data/metadata/nasa_selection.json").read_text())
    if limit is not None:
        records = records[:limit]
    elif len(records) != len(selection["scenes"]):
        raise ValueError("Acquisition is incomplete; use --limit only for an explicitly provisional validation run")
    config = DetectionConfig()
    params = {"started_at": utc_now(), "input_manifest_sha256": sha256(manifest_path),
              "selection_sha256": sha256(root / "data/metadata/nasa_selection.json"),
              "config": asdict(config), "catalog_distance_m": 300, "catalog_time_seconds": 120,
              "sensitivity_correction": "enhancement / sensitivity",
              "sensor_uncertainty": "use supplied V002 UNCERT without dividing by sensitivity again",
              "region_bbox": selection["bbox"], "provisional_limit": limit}
    params["code_sha256"] = {p.name: sha256(p) for p in Path(__file__).parent.glob("*.py")}
    params["environment_sha256"] = sha256(root / "outputs/environment.json")
    params["reference_catalog_sha256"] = {p: sha256(root / "data/metadata" / p) for p in
        ["carbonmapper_scene_plumes.json", "nasa_plume_cmr_same_scenes.json"]}
    write_json(root / "outputs/run_parameters.json", params)
    catalog = _catalog(root)
    nasa_catalog = load_nasa_catalog(root / "data/metadata/nasa_plume_cmr_same_scenes.json")
    summaries, candidates, validation, sensitivity_rows = [], [], [], []
    roi = box(*selection["bbox"])
    for index, record in enumerate(records, start=1):
        scene, files = record["scene"], record["files"]
        for f in files.values():
            if f and sha256(root / f["path"]) != f["sha256"]:
                raise ValueError(f"Input checksum changed: {f['path']}")
        arrays, meta = aligned_rasters(root / files["enhancement"]["path"],
                                       root / files["sensitivity"]["path"],
                                       root / files["uncertainty"]["path"])
        t = Affine(*meta["transform"])
        roi_geom = transform_geom("EPSG:4326", meta["crs"], mapping(roi))
        inside = geometry_mask([roi_geom], out_shape=arrays["enhancement"].shape, transform=t, invert=True)
        raw_valid = np.isfinite(arrays["enhancement"]) & inside
        arrays["enhancement"][~inside] = np.nan
        qmask, qinfo = quality_mask_for_enhancement(root / files["quality"]["path"], root / files["enhancement"]["path"])
        write_json(root / "outputs/quality" / (scene["name"] + ".json"), qinfo)
        result = screen_enhancements(arrays["enhancement"], sensitivity=arrays["sensitivity"],
                                     uncertainty=arrays["uncertainty"], quality_mask=qmask, config=config)
        scene_rows = []
        for candidate in result.candidates:
            geometry = component_geometry(result.labels, candidate.label, t, meta["crs"])
            center = geometry.centroid
            matches = polygon_catalog_matches(geometry, scene["timestamp"], catalog)
            same = [m for m in matches if m["association"] == "same_acquisition_neighborhood"]
            nasa_matches = [m.to_dict() for m in match_nasa_catalog(geometry, scene["timestamp"], nasa_catalog)]
            mask = result.labels == candidate.label
            annulus = ndimage.binary_dilation(mask, iterations=8) & ~ndimage.binary_dilation(mask, iterations=2) & result.valid
            ring = result.corrected[annulus]
            ring_median = float(np.median(ring)) if len(ring) >= 32 else None
            ring_sigma = float(1.4826 * np.median(np.abs(ring - ring_median))) if ring_median is not None else None
            contrast = ((candidate.median_ppm_m - ring_median) / max(ring_sigma, 1)) if ring_sigma is not None else None
            flags = list(candidate.flags)
            sens_median = float(np.median(arrays["sensitivity"][mask]))
            if sens_median < .3:
                flags.append("large_sensitivity_correction")
            if contrast is None:
                flags.append("insufficient_local_annulus")
            elif contrast < 3:
                flags.append("weak_local_annulus_contrast")
            if project(MERCATOR, roi.boundary).distance(project(MERCATOR, geometry)) < 1000:
                flags.append("near_region_boundary")
            previously_documented = bool(same or nasa_matches)
            row = {"candidate_id": f"MH-{index:02d}-{candidate.label:04d}", "scene_id": scene["name"],
                   "observed_at": scene["timestamp"], "role": scene["role"],
                   "satellite": "ISS", "instrument": "EMIT", "method": METHOD,
                   "latitude": center.y, "longitude": center.x,
                   "location_type": "enhancement support centroid, not an inferred source",
                   **candidate.to_dict(), "flags": flags,
                   "area_m2": float(project(MERCATOR, geometry).area),
                   "sensitivity_median": sens_median,
                   "sensor_uncertainty_median_ppm_m": float(np.median(arrays["uncertainty"][mask])),
                   "local_annulus_pixels": int(len(ring)), "local_annulus_median_ppm_m": ring_median,
                   "local_annulus_robust_sigma_ppm_m": ring_sigma,
                   "local_annulus_contrast_sigma": contrast,
                   "catalog_matches": matches, "nasa_plume_outline_matches": nasa_matches, "geometry": mapping(geometry),
                   "category": "E" if previously_documented else "C",
                   "novelty": "associated with a published observation" if previously_documented else "not established; finite catalog snapshot only",
                   "possible_source": None, "facility": None, "emission_rate_kg_h": None,
                   "independent_sensor_corroboration": False,
                   "quality_assessment": "passes five named L2A binary flags and sensor uncertainty/sensitivity screening",
                   "alternative_explanations": ["surface spectral retrieval artifact", "residual clouds or shadow", "image striping", "multiple testing and retrieval noise"],
                   "unchecked": ["independent radiance spectral fit", "surface reflectance comparison", "independent wind field", "another sensor", "facility attribution"],
                   "initial_assessment": "published same-acquisition neighborhood or NASA outline association; not independent confirmation" if previously_documented else "ambiguous enhancement hypothesis requiring spectral and independent observation checks",
                   "source_files": files}
            scene_rows.append(row)
            write_json(root / "outputs/dossiers" / (row["candidate_id"] + ".json"), row)
        # Known catalog points are source-head estimates, not pixel truth labels.
        expected = scene.get("catalog_ch4_matches_in_bbox", [])
        expected_ids = []
        recovered_ids = set()
        reference_quality = []
        for r in expected:
            rid = r if isinstance(r, str) else r.get("plume_id", r.get("id"))
            expected_ids.append(rid)
            reference = next((r for r in catalog if r["plume_id"] == rid), None)
            head_usable = None
            if reference:
                lon, lat = reference["geometry_json"]["coordinates"]
                native = transform_geom("EPSG:4326", meta["crs"], mapping(Point(lon, lat)))
                col, row_index = (~t) * native["coordinates"]
                row_index, col = int(np.floor(row_index)), int(np.floor(col))
                head_usable = bool(0 <= row_index < result.valid.shape[0] and 0 <= col < result.valid.shape[1] and result.valid[row_index, col])
            reference_quality.append({"catalog_id": rid, "source_head_pixel_usable": head_usable})
            if any(any(m["catalog_id"] == rid and m["association"] == "same_acquisition_neighborhood"
                       for m in c["catalog_matches"]) for c in scene_rows):
                recovered_ids.add(rid)
        valid_values = result.corrected[result.valid]
        summary = {"granule": scene["name"], "observedAt": scene["timestamp"], "role": scene["role"],
                   "roi_unmasked_pixels": int(raw_valid.sum()), "valid_pixels": int(result.valid.sum()),
                   "quality_retained_fraction_in_roi": float(result.valid.sum() / raw_valid.sum()) if raw_valid.any() else 0.,
                   "median_ppm_m": float(np.median(valid_values)) if len(valid_values) else None,
                   "peak_ppm_m": float(np.max(valid_values)) if len(valid_values) else None,
                   "background_scale_ppm_m": result.diagnostics["global_background_scale_ppm_m"],
                   "candidate_count": len(scene_rows), "catalog_associated_components": sum(c["category"] == "E" for c in scene_rows),
                   "unmatched_components": sum(c["category"] == "C" for c in scene_rows),
                   "known_roi_points": len(expected_ids), "recovered_known_points": len(recovered_ids),
                   "known_head_pixels_usable": sum(r["source_head_pixel_usable"] is True for r in reference_quality),
                   "nasa_cloud_percent": scene.get("nasa_cloud_cover_pct", scene.get("cmr_granule", {}).get("cloud_cover")),
                   "cm_cloud_percent": scene.get("cm_scene", {}).get("cloud_cover_pct_assessed"),
                   "grid_shape": meta["shape"], "grid_crs": meta["crs"],
                   "quality_grid_check": "passed exact GLT and integer-window alignment",
                   "diagnostics": result.diagnostics}
        summary["map"] = _plot_scene(root, index, scene, meta, result, scene_rows, catalog)
        summaries.append(summary)
        if scene["role"] in ["positive_validation", "control_validation"]:
            validation.append({"granule": scene["name"], "role": scene["role"],
                               "known_points": len(expected_ids), "recovered_points": len(recovered_ids),
                               "components": len(scene_rows), "usable_pixels": int(result.valid.sum()),
                               "quality_grid_check": "pass", "known_point_ids": expected_ids,
                               "recovered_point_ids": sorted(recovered_ids),
                               "reference_head_quality": reference_quality,
                               "interpretation": "known-example neighborhood recovery, not independent sensor validation" if expected_ids else "catalog-negative control; screened components are not established false positives"})
        for sigma in [3., 7.]:
            alternate = screen_enhancements(arrays["enhancement"], sensitivity=arrays["sensitivity"],
                                             uncertainty=arrays["uncertainty"], quality_mask=qmask,
                                             config=replace(config, background_sigma_multiplier=sigma, min_sensor_snr=sigma))
            sensitivity_rows.append({"granule": scene["name"], "role": scene["role"], "sigma": sigma,
                                     "component_count": len(alternate.candidates),
                                     "baseline_component_count": len(scene_rows)})
            del alternate
        candidates.extend(scene_rows)
        write_json(root / "outputs/scene_metrics.json", summaries)
        write_json(root / "outputs/candidates.json", candidates)
        write_json(root / "outputs/validation.json", validation)
        write_json(root / "outputs/threshold_sensitivity.json", sensitivity_rows)
        print(f"Analyzed {index}/{len(records)} {scene['timestamp']}: {result.valid.sum():,} usable pixels, {len(scene_rows)} components, {len(recovered_ids)}/{len(expected_ids)} known points associated", flush=True)
        del arrays, result, qmask, inside, raw_valid
        gc.collect()
    _finalize(root, summaries, candidates, validation, sensitivity_rows, params)
    return summaries, candidates


def _finalize(root, scenes, candidates, validation, sensitivity, params):
    # Preserve nested evidence in JSON; CSV is a flat inspection register.
    pd.DataFrame([{k: json.dumps(v) if isinstance(v, (list, dict, tuple)) else v for k, v in row.items()}
                  for row in scenes]).to_csv(root / "outputs/scene_metrics.csv", index=False)
    fields = ["candidate_id", "scene_id", "observed_at", "role", "category", "latitude", "longitude",
              "peak_ppm_m", "median_ppm_m", "pixel_count", "area_m2", "median_sensor_snr",
              "sensor_uncertainty_median_ppm_m", "local_annulus_contrast_sigma", "novelty", "flags"]
    pd.DataFrame([{k: json.dumps(c[k]) if isinstance(c[k], list) else c[k] for k in fields} for c in candidates],
                 columns=fields).to_csv(root / "outputs/candidates.csv", index=False)
    write_json(root / "outputs/candidates.geojson", {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": c["candidate_id"], "geometry": c["geometry"],
         "properties": {k: c[k] for k in fields if k != "flags"}} for c in candidates]})
    pd.DataFrame(validation).to_csv(root / "outputs/validation.csv", index=False)
    pd.DataFrame(sensitivity).to_csv(root / "outputs/threshold_sensitivity.csv", index=False)
    summary = {"finished_at": utc_now(), "scenes_analyzed": len(scenes),
               "date_start": min(s["observedAt"] for s in scenes), "date_end": max(s["observedAt"] for s in scenes),
               "distinct_dates": len({s["observedAt"][:10] for s in scenes}),
               "roles": {role: sum(s["role"] == role for s in scenes) for role in ["positive_validation", "control_validation", "search"]},
               "usable_pixel_observations": sum(s["valid_pixels"] for s in scenes),
               "screened_components": len(candidates), "category_E": sum(c["category"] == "E" for c in candidates),
               "category_C": sum(c["category"] == "C" for c in candidates),
               "independently_corroborated_new_sources": 0, "novelty_established": False,
               "positive_scenes_with_association": sum(v["recovered_points"] > 0 for v in validation if v["role"] == "positive_validation"),
               "positive_scenes_examined": sum(v["role"] == "positive_validation" for v in validation),
               "control_scenes_examined": sum(v["role"] == "control_validation" for v in validation),
               "validation_scope": "IO/quality alignment and limited known-example plus catalog-negative checks; no population sensitivity or false-positive calibration",
               "search_scope": "16 frozen granules, clipped to the fixed ROI; exploratory hypotheses only",
               "provisional": params["provisional_limit"] is not None}
    write_json(root / "outputs/run_summary.json", summary)

