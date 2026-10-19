"""E02: diagnose known-example misses without changing the frozen detector.

Runs the same 3/5/7 multiplier sensitivity checks on the two positive validation
scenes, inspecting all scene-scoped Carbon Mapper heads and exact NASA CMR plume
outline polygons. Local annuli provide a different background diagnostic on the
same retrieval; they are not an independent sensor or spectral confirmation.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import datetime
import gc
import json
from pathlib import Path

import h5netcdf
import numpy as np
import pandas as pd
from pyproj import Transformer
from rasterio.features import geometry_mask, shapes
from rasterio.transform import Affine
from scipy import ndimage
from shapely.geometry import Point, Polygon, box, mapping, shape
from shapely.ops import transform as project, unary_union

from methane_hunter.data import aligned_rasters, sha256, utc_now, write_json
from methane_hunter.detection import DetectionConfig, screen_enhancements
from methane_hunter.quality import quality_mask_for_enhancement


FORWARD = Transformer.from_crs("EPSG:4326", "EPSG:32613", always_xy=True)
BACKWARD = Transformer.from_crs("EPSG:32613", "EPSG:4326", always_xy=True)


def time_difference(a, b):
    return abs((datetime.fromisoformat(a.replace("Z", "+00:00"))
                - datetime.fromisoformat(b.replace("Z", "+00:00"))).total_seconds())


def number(values, operation):
    values = np.asarray(values)
    values = values[np.isfinite(values)]
    return float(operation(values)) if values.size else None


def cmr_outline(entry):
    """Parse supplied CMR polygon vertices (latitude longitude), never boxes."""
    polygons = []
    for group in entry.get("polygons", []):
        if len(group) != 1:
            raise ValueError("CMR multi-ring outline needs explicit interpretation")
        vertices = np.asarray([float(x) for x in group[0].split()]).reshape(-1, 2)
        polygon = Polygon([(lon, lat) for lat, lon in vertices])
        if not polygon.is_valid:
            raise ValueError("Invalid NASA CMR outline; no silent geometry repair")
        polygons.append(polygon)
    if not polygons:
        raise ValueError("NASA plume record lacks a polygon outline")
    return unary_union(polygons)


def local_component_geometries(result, transform):
    output = {}
    for candidate in result.candidates:
        r0, c0, r1, c1 = candidate.bbox_rc
        support = result.labels[r0:r1, c0:c1] == candidate.label
        local_transform = transform * Affine.translation(c0, r0)
        polygons = [shape(geometry) for geometry, value in shapes(
            support.astype("uint8"), mask=support, transform=local_transform) if value == 1]
        geometry = unary_union(polygons)
        output[candidate.label] = (geometry, project(FORWARD.transform, geometry))
    return output


def point_window(lon, lat, transform, raster_shape, radius=1500.):
    """Use a local metric disk; pixel centers are tested in UTM meters."""
    x0, y0 = FORWARD.transform(lon, lat)
    circle = project(BACKWARD.transform, Point(x0, y0).buffer(radius, resolution=32))
    west, south, east, north = circle.bounds
    inverse = ~transform
    corners = [inverse * (x, y) for x, y in [(west, south), (west, north), (east, south), (east, north)]]
    c0 = max(0, int(np.floor(min(x[0] for x in corners))) - 1)
    c1 = min(raster_shape[1], int(np.ceil(max(x[0] for x in corners))) + 1)
    r0 = max(0, int(np.floor(min(x[1] for x in corners))) - 1)
    r1 = min(raster_shape[0], int(np.ceil(max(x[1] for x in corners))) + 1)
    if r1 <= r0 or c1 <= c0:
        return (slice(0, 0), slice(0, 0)), np.empty((0, 0)), Point(x0, y0)
    rows, cols = np.meshgrid(np.arange(r0, r1) + .5, np.arange(c0, c1) + .5, indexing="ij")
    longitude = transform.a * cols + transform.b * rows + transform.c
    latitude = transform.d * cols + transform.e * rows + transform.f
    xs, ys = FORWARD.transform(longitude, latitude)
    distances = np.hypot(xs - x0, ys - y0)
    return (slice(r0, r1), slice(c0, c1)), distances, Point(x0, y0)


def criterion_diagnosis(usable, absolute, background, sensor, selected, retained):
    """Attribute software exclusion criteria without explaining the atmosphere."""
    if usable == 0:
        return "no pixels survive ROI, nodata, quality, sensitivity, and uncertainty eligibility"
    if retained:
        return "retained component in the specified neighborhood; association only"
    if selected:
        return "threshold pixels exist but no retained >=4-pixel component is associated with this neighborhood"
    if absolute == 0:
        return "no usable pixel exceeds the fixed 500 ppm m enhancement floor"
    if background == 0 and sensor == 0:
        return "local robust-background and supplied sensor-noise criteria each exclude all usable pixels"
    if sensor == 0:
        return "supplied sensor-noise criterion excludes all usable pixels"
    if background == 0:
        return "local robust-background criterion excludes all usable pixels"
    return "individual criteria have passing pixels but no pixel passes their conjunction"


def head_flag_contexts(mask_path, head_contexts):
    """Read exact GLT-mapped flag values only for the small head neighborhoods."""
    output = {}
    with h5netcdf.File(mask_path, "r") as ds:
        cube = ds.variables["mask"][:]
        labels = [value.decode() if isinstance(value, bytes) else str(value)
                  for value in ds.groups["sensor_band_parameters"].variables["mask_bands"][:]]
        selected = [(i, label) for i, label in enumerate(labels)
                    if label.lower() in {"cloud flag", "cirrus flag", "water flag", "spacecraft flag", "dilated cloud flag"}]
        loc = ds.groups["location"]
        for identity, (window, _, _) in head_contexts.items():
            x, y = loc.variables["glt_x"][window], loc.variables["glt_y"][window]
            valid = np.isfinite(x) & np.isfinite(y) & (x > 0) & (y > 0)
            rr, cc = y[valid].astype(int) - 1, x[valid].astype(int) - 1
            mapped = {}
            for index, label in selected:
                values = np.full(x.shape, np.nan)
                values[valid] = cube[rr, cc, index]
                mapped[label] = values
            output[identity] = mapped
    return output


def main(root="."):
    root = Path(root)
    manifest_path = root / "data/nasa_input_manifest.json"
    selection_path = root / "data/metadata/nasa_selection.json"
    cm_path = root / "data/metadata/carbonmapper_scene_plumes.json"
    nasa_path = root / "data/metadata/nasa_plume_cmr_same_scenes.json"
    records = [x for x in json.loads(manifest_path.read_text()) if x["scene"]["role"] == "positive_validation"][:2]
    if len(records) != 2:
        raise ValueError("E02 requires both complete positive-validation scene records")
    roi_bounds = json.loads(selection_path.read_text())["bbox"]
    cm_snapshot = json.loads(cm_path.read_text())
    nasa_snapshot = json.loads(nasa_path.read_text())
    cm_rows = [row for query in cm_snapshot["queries"] for row in query["response"]["items"]]
    # Preserve publication identifiers when the same point appears in more than one scoped query.
    cm_rows = list({row["id"]: row for row in cm_rows}.values())
    nasa_rows = [row for query in nasa_snapshot["queries"] for row in query["response"]["feed"]["entry"]]
    nasa_rows = list({row["id"]: row for row in nasa_rows}.values())
    output = {
        "experiment": "E02 known-example exclusion diagnostics",
        "started_at": utc_now(), "baseline_config_unchanged": asdict(DetectionConfig()),
        "threshold_multipliers": [3., 5., 7.], "head_neighborhood_radii_m": [300., 1000.],
        "local_annulus_inner_outer_m": [1000., 1500.], "roi_bbox": roi_bounds,
        "inputs": {str(path.relative_to(root)): sha256(path) for path in [manifest_path, selection_path, cm_path, nasa_path]},
        "command": "PYTHONPATH=src .venv/bin/python scripts/diagnose_known.py",
        "script_sha256": sha256(Path(__file__)),
        "scope": "two positive scenes; all scene-scoped CM heads and same-start-time NASA CMR outline polygons",
        "interpretation": "retrieval-level and software-threshold diagnostics; not independent methane validation",
        "limitations": [
            "NASA and Carbon Mapper use different retrieval, masking, and catalog conventions on the same EMIT observations",
            "Catalog source heads are not pixel truth labels; plume signal may lie downwind beyond the chosen radii",
            "Sensor-noise uncertainty and robust MAD criteria do not represent all retrieval errors or calibrated false-alarm rates",
            "Local annulus values come from the same retrieved raster and can include plume signal or surface artifacts",
            "NASA CMR outlines are published plume-complex polygons, not independently measured truth masks",
            "A missed or associated known observation does not validate an unmatched finding or establish novelty",
        ],
        "point_diagnostics": [], "nasa_polygon_diagnostics": [], "scene_thresholds": [],
    }
    for record in records:
        scene, files = record["scene"], record["files"]
        for obj in files.values():
            if obj and sha256(root / obj["path"]) != obj["sha256"]:
                raise ValueError("Input hash mismatch")
        arrays, meta = aligned_rasters(root / files["enhancement"]["path"], root / files["sensitivity"]["path"], root / files["uncertainty"]["path"])
        transform = Affine(*meta["transform"])
        if meta["crs"] != "EPSG:4326":
            raise ValueError("E02 diagnostic currently expects the observed EPSG:4326 EMIT grid")
        qmask, quality = quality_mask_for_enhancement(root / files["quality"]["path"], root / files["enhancement"]["path"])
        inside = geometry_mask([mapping(box(*roi_bounds))], transform=transform,
                               out_shape=arrays["enhancement"].shape, invert=True)
        raw = arrays["enhancement"]
        sensitivity = arrays["sensitivity"]
        uncertainty = arrays["uncertainty"]
        raw_in_roi = np.where(inside, raw, np.nan)
        unfiltered_corrected = np.full(raw.shape, np.nan)
        prelim = inside & np.isfinite(raw) & np.isfinite(sensitivity) & (sensitivity > .1)
        np.divide(raw, sensitivity, out=unfiltered_corrected, where=prelim)
        heads = [r for r in cm_rows if time_difference(scene["timestamp"], r["scene_timestamp"]) <= 1]
        outlines = [r for r in nasa_rows if time_difference(scene["timestamp"], r["time_start"]) <= 1]
        head_contexts = {}
        for head in heads:
            lon, lat = head["geometry_json"]["coordinates"]
            window, distances, point = point_window(lon, lat, transform, raw.shape)
            head_contexts[head["id"]] = (window, distances, point)
        flag_contexts = head_flag_contexts(root / files["quality"]["path"], head_contexts)
        for sigma in [3., 5., 7.]:
            config = replace(DetectionConfig(), background_sigma_multiplier=sigma, min_sensor_snr=sigma)
            result = screen_enhancements(raw_in_roi, sensitivity=sensitivity, uncertainty=uncertainty,
                                         quality_mask=qmask, config=config)
            components = local_component_geometries(result, transform)
            pre_min_labels, _ = ndimage.label(result.valid & (result.corrected >= result.threshold),
                                               structure=np.ones((3, 3), dtype="uint8"))
            pre_min_sizes = np.bincount(pre_min_labels.ravel())
            output["scene_thresholds"].append({"scene": scene["name"], "timestamp": scene["timestamp"], "sigma": sigma,
                                                "usable_pixels": int(result.valid.sum()), "components": len(result.candidates),
                                                "supra_threshold_pixels": result.diagnostics["supra_threshold_pixels"],
                                                "known_cm_heads": len(heads), "known_nasa_outlines": len(outlines)})
            for head in heads:
                window, distances, point = head_contexts[head["id"]]
                roi_local = inside[window]
                valid = result.valid[window]
                corr = result.corrected[window]
                bg = result.background[window]
                scale = result.background_scale[window]
                unc = uncertainty[window]
                excess = corr - bg
                sensor_snr = np.divide(excess, unc, out=np.full(excess.shape, np.nan), where=valid)
                bg_contrast = np.divide(excess, scale, out=np.full(excess.shape, np.nan), where=valid)
                annulus = (distances > 1000.) & (distances <= 1500.) & valid
                annulus_values = corr[annulus]
                annulus_median = float(np.median(annulus_values)) if annulus_values.size >= 32 else None
                annulus_sigma = max(float(1.4826 * np.median(np.abs(annulus_values - annulus_median))), 1.) if annulus_median is not None else None
                for radius in [300., 1000.]:
                    disk = distances <= radius
                    disk_roi = disk & roi_local
                    usable = disk & valid
                    absolute = usable & (corr >= config.min_enhancement_ppm_m)
                    background_ok = usable & (bg_contrast >= sigma)
                    sensor_ok = usable & (sensor_snr >= sigma)
                    selected = usable & (corr >= result.threshold[window])
                    unfiltered_labels = np.unique(pre_min_labels[window][disk])
                    unfiltered_labels = unfiltered_labels[unfiltered_labels > 0]
                    component_sizes = sorted([int(pre_min_sizes[label]) for label in unfiltered_labels], reverse=True)
                    nearby = [label for label, (_, metric) in components.items() if metric.distance(point) <= radius]
                    all_distances = [metric.distance(point) for _, metric in components.values()]
                    raw_finite = disk_roi & np.isfinite(raw[window])
                    qpass = raw_finite & qmask[window]
                    context_corrected = unfiltered_corrected[window]
                    annulus_contrast = ((number(corr[usable], np.max) - annulus_median) / annulus_sigma
                                        if usable.any() and annulus_sigma is not None else None)
                    row = {
                        "kind": "CM_head_neighborhood", "scene": scene["name"], "timestamp": scene["timestamp"],
                        "catalog_id": head["plume_id"], "catalog_record_id": head["id"],
                        "longitude": head["geometry_json"]["coordinates"][0], "latitude": head["geometry_json"]["coordinates"][1],
                        "radius_m": radius, "sigma": sigma,
                        "disk_grid_pixels": int(disk.sum()), "disk_roi_pixels": int(disk_roi.sum()),
                        "raw_finite_pixels": int(raw_finite.sum()), "quality_pass_pixels": int(qpass.sum()),
                        "quality_pass_fraction_of_raw_finite": float(qpass.sum() / raw_finite.sum()) if raw_finite.any() else None,
                        "usable_pixels": int(usable.sum()),
                        "sensitivity_gt_point1_pixels": int((raw_finite & np.isfinite(sensitivity[window]) & (sensitivity[window] > .1)).sum()),
                        "raw_max_ppm_m": number(raw[window][raw_finite], np.max),
                        "sensitivity_corrected_max_without_quality_ppm_m": number(context_corrected[disk_roi], np.max),
                        "sensitivity_corrected_max_usable_ppm_m": number(corr[usable], np.max),
                        "minimum_usable_uncertainty_ppm_m": number(unc[usable], np.min),
                        "median_usable_uncertainty_ppm_m": number(unc[usable], np.median),
                        "max_background_subtracted_sensor_snr": number(sensor_snr[usable], np.max),
                        "max_local_background_contrast_sigma": number(bg_contrast[usable], np.max),
                        "absolute_floor_pass_pixels": int(absolute.sum()),
                        "robust_background_pass_pixels": int(background_ok.sum()),
                        "sensor_noise_pass_pixels": int(sensor_ok.sum()),
                        "joint_threshold_pass_pixels": int(selected.sum()),
                        "threshold_component_sizes_before_min_pixel_filter": component_sizes,
                        "largest_threshold_component_before_min_pixel_filter": max(component_sizes) if component_sizes else 0,
                        "quality_flag_counts_in_disk": {label: {
                            "flagged_raw_finite_pixels": int(np.count_nonzero(raw_finite & (values == 1))),
                            "unknown_raw_finite_pixels": int(np.count_nonzero(raw_finite & ~np.isin(values, [0, 1]))),
                        } for label, values in flag_contexts[head["id"]].items()},
                        "retained_component_count_within_radius": len(nearby), "retained_component_labels": nearby,
                        "nearest_retained_component_distance_m": float(min(all_distances)) if all_distances else None,
                        "neighborhood_associated": bool(nearby),
                        "diagnosis": criterion_diagnosis(int(usable.sum()), int(absolute.sum()), int(background_ok.sum()),
                                                         int(sensor_ok.sum()), int(selected.sum()), nearby),
                        "annulus_usable_pixels": int(annulus_values.size),
                        "annulus_median_ppm_m": annulus_median, "annulus_robust_sigma_ppm_m": annulus_sigma,
                        "max_usable_enhancement_annulus_contrast_sigma": annulus_contrast,
                        "annulus_interpretation": "same-retrieval local background check; not independent confirmation",
                    }
                    output["point_diagnostics"].append(row)
            for entry in outlines:
                geometry = cmr_outline(entry)
                support = geometry_mask([mapping(geometry)], transform=transform, out_shape=raw.shape, invert=True)
                support_roi = support & inside
                usable = support & result.valid
                intersecting = [label for label, (candidate_geo, _) in components.items()
                                if candidate_geo.intersects(geometry) and candidate_geo.intersection(geometry).area > 0]
                excess = result.corrected - result.background
                values = result.corrected[usable]
                sensor_values = excess[usable] / uncertainty[usable]
                background_values = excess[usable] / result.background_scale[usable]
                selected = usable & (result.corrected >= result.threshold)
                unfiltered_labels = np.unique(pre_min_labels[support_roi])
                unfiltered_labels = unfiltered_labels[unfiltered_labels > 0]
                component_sizes = sorted([int(pre_min_sizes[label]) for label in unfiltered_labels], reverse=True)
                absolute_count = int(np.count_nonzero(values >= config.min_enhancement_ppm_m))
                background_count = int(np.count_nonzero(background_values >= sigma))
                sensor_count = int(np.count_nonzero(sensor_values >= sigma))
                row = {
                    "kind": "NASA_CMR_plume_outline", "scene": scene["name"], "timestamp": scene["timestamp"],
                    "catalog_id": entry["title"], "catalog_record_id": entry["id"], "sigma": sigma,
                    "outline_geometry": mapping(geometry), "outline_pixel_centers": int(support.sum()),
                    "outline_roi_pixel_centers": int(support_roi.sum()), "usable_pixels": int(usable.sum()),
                    "raw_max_ppm_m": number(raw[support_roi & np.isfinite(raw)], np.max),
                    "sensitivity_corrected_max_without_quality_ppm_m": number(unfiltered_corrected[support_roi], np.max),
                    "sensitivity_corrected_max_usable_ppm_m": number(values, np.max),
                    "max_background_subtracted_sensor_snr": number(sensor_values, np.max),
                    "max_local_background_contrast_sigma": number(background_values, np.max),
                    "absolute_floor_pass_pixels": absolute_count, "robust_background_pass_pixels": background_count,
                    "sensor_noise_pass_pixels": sensor_count, "joint_threshold_pass_pixels": int(selected.sum()),
                    "threshold_component_sizes_before_min_pixel_filter": component_sizes,
                    "largest_threshold_component_before_min_pixel_filter": max(component_sizes) if component_sizes else 0,
                    "retained_component_count_intersecting_outline": len(intersecting), "retained_component_labels": intersecting,
                    "outline_associated": bool(intersecting),
                    "diagnosis": criterion_diagnosis(int(usable.sum()), absolute_count, background_count, sensor_count,
                                                     int(selected.sum()), intersecting),
                    "overlap_interpretation": "positive-area intersection of component pixel polygon and supplied NASA outline; never a raster bbox match",
                }
                output["nasa_polygon_diagnostics"].append(row)
            print(f"E02 {scene['timestamp']} sigma={sigma:g}: {len(result.candidates)} retained components", flush=True)
            del result, components, pre_min_labels, pre_min_sizes
            gc.collect()
        del arrays, qmask, raw_in_roi, unfiltered_corrected, inside
        gc.collect()
    output["summary"] = []
    for scene in records:
        name = scene["scene"]["name"]
        for sigma in [3., 5., 7.]:
            points = [r for r in output["point_diagnostics"] if r["scene"] == name and r["sigma"] == sigma]
            outlines = [r for r in output["nasa_polygon_diagnostics"] if r["scene"] == name and r["sigma"] == sigma]
            output["summary"].append({
                "scene": name, "sigma": sigma,
                "cm_heads_associated_300m": sum(r["neighborhood_associated"] for r in points if r["radius_m"] == 300.),
                "cm_heads_associated_1000m": sum(r["neighborhood_associated"] for r in points if r["radius_m"] == 1000.),
                "cm_heads_total": sum(r["radius_m"] == 300. for r in points),
                "nasa_outlines_intersected": sum(r["outline_associated"] for r in outlines),
                "nasa_outlines_total": len(outlines),
            })
    output["finished_at"] = utc_now()
    write_json(root / "outputs/known_diagnostics.json", output)
    rows = output["point_diagnostics"] + output["nasa_polygon_diagnostics"]
    pd.DataFrame([{k: json.dumps(v) if isinstance(v, (dict, list, tuple)) else v for k, v in row.items()} for row in rows]).to_csv(root / "outputs/known_diagnostics.csv", index=False)
    print(json.dumps(output["summary"], indent=2), flush=True)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    main(parser.parse_args().root)
