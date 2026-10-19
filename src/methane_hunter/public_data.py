"""Acquire bounded, numeric NASA GHGC exports of published EMIT plume crops.

These are catalog-selected PLM crops, frequently with only plume-support pixels
valid. They cannot replace full-scene CH4ENH/SENS/UNCERT observations or support
an uncataloged-emission search. The public raster API is a derived export of a
protected source COG, not a byte-identical download of that original COG.

Exports are requested at source dimensions with nearest-neighbor sampling, no
rescale/color map, and a validity mask. Exact export hashes, request parameters,
source grid checks, and provider metadata are retained for reproducibility.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
from urllib.parse import urlencode, parse_qs, urlsplit

import numpy as np
import rasterio
from rasterio.enums import ColorInterp

from .data import DownloadBudget, clean_url, sha256, utc_now, write_json


COLLECTION = "emit-ch4plume-v2"
ASSET = "ch4-plume-emissions"
RASTER_API = "https://earth.gov/eic/api/raster"
TOTAL_DOWNLOAD_LIMIT = 5_000_000_000


def native_export_request(item_id: str, width: int, height: int) -> tuple[str, dict]:
    """Construct a safe, explicit native-size scientific TIFF request."""
    if not re.fullmatch(r"EMIT_L2B_CH4PLM_002_[A-Za-z0-9_]+", item_id):
        raise ValueError("Expected an EMIT V002 plume item identifier")
    if (isinstance(width, bool) or isinstance(height, bool)
            or not isinstance(width, int) or not isinstance(height, int)
            or width <= 0 or height <= 0):
        raise ValueError("Native source width and height must be positive integers")
    endpoint = f"{RASTER_API}/collections/{COLLECTION}/items/{item_id}/preview.tif"
    parameters = {
        "assets": ASSET,
        "width": width,
        "height": height,
        "max_size": max(width, height),
        "resampling": "nearest",
        "return_mask": "true",
        "unscale": "false",
    }
    return endpoint, parameters


def _source_grid(scene: dict, item: dict | None) -> dict:
    """Read native grid from provider STAC, or an explicitly saved info response."""
    asset = (item or {}).get("assets", {}).get(ASSET, {})
    info = scene.get("source_info", scene.get("native_info", {}))
    if ASSET in info:
        info = info[ASSET]
    shape = asset.get("proj:shape") or scene.get("source_shape") or scene.get("native_shape")
    if shape is None and "height" in scene and "width" in scene:
        shape = [scene["height"], scene["width"]]
    if shape is None and "height" in info and "width" in info:
        shape = [info["height"], info["width"]]
    if shape is None or len(shape) != 2:
        raise ValueError(f"No verified native source dimensions for {scene['name']}")
    height, width = shape
    native_export_request(scene["name"], width, height)  # validate integer dimensions
    bounds = asset.get("proj:bbox") or scene.get("source_bounds") or info.get("bounds") or (item or {}).get("bbox")
    if (bounds is None or len(bounds) != 4
            or not all(math.isfinite(float(x)) for x in bounds)):
        raise ValueError("Source bounds are required to verify georeferencing")
    transform = asset.get("proj:transform") or scene.get("source_transform") or info.get("transform")
    epsg = asset.get("proj:epsg") or scene.get("source_epsg", 4326)
    if epsg != 4326:
        raise ValueError("This public-crop acquisition currently expects EPSG:4326 sources")
    dtype = info.get("dtype") or asset.get("raster:bands", [{}])[0].get("data_type")
    if dtype is not None and dtype not in ("float32", "float64"):
        raise ValueError("Provider source must be floating-point scientific enhancement data")
    return {"shape": [height, width], "bounds": list(bounds), "transform": transform,
            "epsg": epsg, "source_dtype": dtype,
            "source_nodata": asset.get("raster:bands", [{}])[0].get("nodata", -9999.),
            "source_asset": clean_url(asset["href"]) if asset.get("href", "").startswith("https://") else asset.get("href")}


def validate_public_export(path, source_grid: dict) -> dict:
    """Reject rendered imagery, unexpected grids, and ambiguous additional bands.

    Passing these checks verifies numerical packaging and alignment. It does not
    independently validate the NASA methane retrieval or identify cloud effects.
    """
    with rasterio.open(path) as ds:
        if ds.crs is None or ds.crs.to_epsg() != source_grid["epsg"]:
            raise ValueError("Export CRS does not match the source grid")
        if [ds.height, ds.width] != list(source_grid["shape"]):
            raise ValueError("Export dimensions differ from native source dimensions")
        if ds.dtypes[0] not in ("float32", "float64"):
            raise ValueError("Export band 1 is not floating-point scientific data")
        if ds.count not in (1, 2):
            raise ValueError("Expected one scientific band and at most one alpha band")
        if ds.count == 2 and ds.colorinterp[1] != ColorInterp.alpha:
            raise ValueError("Additional export band is not identified as an alpha mask")
        if not np.allclose(ds.bounds, source_grid["bounds"], rtol=0, atol=1e-9):
            raise ValueError("Export bounds do not match source bounds")
        transform = source_grid.get("transform")
        if transform is not None:
            expected_affine = list(transform)[:6]
            if len(expected_affine) != 6 or not np.allclose(list(ds.transform)[:6], expected_affine, rtol=0, atol=1e-10):
                raise ValueError("Export affine transform does not match source grid")
        scale, offset = ds.scales[0], ds.offsets[0]
        if scale != 1 or offset != 0:
            raise ValueError("Unexpected band scale/offset requires explicit scientific handling")
        data = ds.read(1, masked=True)
        valid = ~np.ma.getmaskarray(data) & np.isfinite(data.data)
        # GHGC float alpha TIFF exports may advertise mask_flags=all_valid and
        # nodata=None; preserve the provider's explicit -9999 missing sentinel.
        if source_grid.get("source_nodata") is not None:
            valid &= data.data != source_grid["source_nodata"]
        if ds.count == 2:
            alpha = ds.read(2)
            valid &= np.isfinite(alpha) & (alpha > 0)
        values = data.data[valid]
        return {
            "checked_at": utc_now(), "native_dimensions_preserved": True,
            "native_grid_preserved": True, "shape": [ds.height, ds.width],
            "crs": str(ds.crs), "transform": list(ds.transform)[:6],
            "bounds": list(ds.bounds), "dtype": ds.dtypes[0],
            "band_count": ds.count, "color_interpretation": [x.name for x in ds.colorinterp],
            "nodata": ds.nodata if ds.nodata is None or math.isfinite(ds.nodata) else "NaN",
            "valid_pixels": int(valid.sum()), "total_pixels": int(valid.size),
            "valid_fraction": float(valid.mean()) if valid.size else 0.,
            "minimum_ppm_m": float(values.min()) if values.size else None,
            "maximum_ppm_m": float(values.max()) if values.size else None,
            "interpretation": "export packaging/grid checks only; catalog-selected masked plume crop",
        }


def _other_transfers(root: Path, own_ledger: Path) -> int:
    """Share the initial 5 GB cap with other project download ledgers."""
    total = 0
    for path in (root / "data").glob("*download_ledger.json"):
        if path.resolve() != own_ledger.resolve():
            value = json.loads(path.read_text())
            if isinstance(value, dict):
                total += int(value.get("total_bytes", 0))
            else:
                total += sum(int(e.get("transferred_bytes", 0)) for e in value)
    return total


def _adopt_initial_ledger(ledger: Path, root: Path):
    """Retain early public download receipts in the shared DownloadBudget schema."""
    if not ledger.exists():
        return
    value = json.loads(ledger.read_text())
    if not isinstance(value, dict):
        return
    converted = []
    for receipt in value.get("downloads", []):
        original_path = receipt["path"]
        local_path = Path(original_path)
        if not local_path.is_absolute():
            local_path = root / local_path
        # The receipt's exact hash is checked again by DownloadBudget.fetch.
        converted.append({
            "path": str(local_path), "url": clean_url(receipt["url"]),
            "transferred_bytes": int(receipt["bytes"]), "sha256": receipt["sha256"],
            "status": "ok", "started_at": receipt.get("downloaded_at"),
            "finished_at": receipt.get("downloaded_at"),
            "original_receipt": {k: v for k, v in receipt.items() if k != "url"},
            "request_parameters": {k: values[0] if len(values) == 1 else values
                                   for k, values in parse_qs(urlsplit(receipt["url"]).query).items()},
        })
    if sum(e["transferred_bytes"] for e in converted) != int(value.get("total_bytes", 0)):
        raise ValueError("Initial public-download ledger bytes do not reconcile")
    write_json(ledger, converted)


def fetch_public_selected(root=".", *, selection_path=None, session=None):
    """Acquire/reuse the frozen public-crop selection and save its input manifest.

    One process must own all download ledgers during acquisition. The 20-item
    bound here counts exported crops; multiple crops can belong to one actual
    EMIT scene, so it is not a claim of 20 independent observations.
    """
    root = Path(root).resolve()
    selection_path = Path(selection_path) if selection_path else root / "data/metadata/public_crop_selection.json"
    selection = json.loads(selection_path.read_text())
    scenes = selection["scenes"]
    if len(scenes) > 20:
        raise ValueError("Initial public sample cannot exceed 20 crop items")
    names = [scene["name"] for scene in scenes]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate crop items in public selection")
    stac_path = root / selection.get("stac_path", "data/metadata/public_crop_stac.json")
    if not stac_path.exists():
        alternative = root / "data/metadata/public_stac.json"
        if alternative.exists():
            stac_path = alternative
    stac = json.loads(stac_path.read_text()) if stac_path.exists() else {"features": []}
    items = {item["id"]: item for item in stac.get("features", [])}
    manifest_path = root / "data/public_input_manifest.json"
    frozen = json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    frozen_files = {record["scene"]["name"]: record["files"]["enhancement"] for record in frozen}
    ledger = root / "data/public_download_ledger.json"
    _adopt_initial_ledger(ledger, root)
    budget = DownloadBudget(ledger, limit=TOTAL_DOWNLOAD_LIMIT - _other_transfers(root, ledger), session=session)
    manifest = []
    for scene in scenes:
        name = scene["name"]
        item = items.get(name)
        grid = _source_grid(scene, item)
        height, width = grid["shape"]
        endpoint, parameters = native_export_request(name, width, height)
        url = endpoint + "?" + urlencode(parameters)
        destination = root / scene.get("path", f"data/raw/{name}/ghgc_native_scientific.tif")
        if not destination.resolve().is_relative_to((root / "data/raw").resolve()):
            raise ValueError("Public export path must stay inside the raw-data directory")
        entry = budget.fetch(url, destination, expected_sha256=frozen_files.get(name, {}).get("sha256"))
        # Adopted receipts describe the first two requests more precisely than
        # a reconstructed equivalent request; retain their exact benign args.
        actual_parameters = entry.get("request_parameters", parameters)
        checks = validate_public_export(destination, grid)
        record = {
            "scene": scene,
            "stac_id": name,
            "properties": (item or {}).get("properties", {}),
            "files": {
                "enhancement": {"path": str(destination.relative_to(root)),
                                "sha256": entry["sha256"], "bytes": destination.stat().st_size,
                                "url": endpoint, "request_parameters": actual_parameters,
                                "kind": "GHGC numeric scientific raster export; source native dimensions"},
                "uncertainty": None, "sensitivity": None, "quality": None,
            },
            "source": "NASA EMIT V002 CH4PLM via US GHG Center raster API",
            "accessed_at": utc_now(),
            "source_grid": grid,
            "raster_validation": checks,
            "catalog": {"source": "NASA published EMIT plume complex selection",
                        "retrieved_at": selection.get("retrieved_at"),
                        "plume_metadata": scene.get("plume_metadata"),
                        "stac_item": item},
            "limitations": [
                "Catalog-selected PLM crop; not a complete CH4ENH scene",
                "Valid support can be restricted to cataloged plume pixels",
                "No per-pixel sensor uncertainty or sensitivity is provided by this export",
                "No independent cloud/surface quality variables are provided by this export",
                "Unmatched screening components cannot establish uncataloged methane or novelty",
                "No independent wind, spectral, facility, or emission-rate verification",
            ],
        }
        manifest.append(record)
        write_json(manifest_path, manifest)
        print(f"Public crop {len(manifest)}/{len(scenes)}: {name}; {budget.used:,} transferred bytes", flush=True)
    return manifest


def verify_public_manifest(root="."):
    """Verify retained exports against their exact hashes and source grids."""
    root = Path(root)
    manifest = json.loads((root / "data/public_input_manifest.json").read_text())
    for record in manifest:
        obj = record["files"]["enhancement"]
        path = root / obj["path"]
        if sha256(path) != obj["sha256"]:
            raise ValueError(f"Frozen public export was modified: {obj['path']}")
        validate_public_export(path, record["source_grid"])
    return manifest


fetch_selected = fetch_public_selected
