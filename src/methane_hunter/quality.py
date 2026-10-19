"""Map NASA EMIT L2A binary quality flags onto a CH4 enhancement grid.

The mapping follows NASA's one-based GLT sample/line convention, with zero
representing missing lookup. It uses exact grid correspondence and integer
window offsets only; no nearest-latitude approximation or resampling is used.

Primary references (accessed 2026-10-18):
https://nasa.github.io/LPDAAC-Data-Resources/external/How_to_use_EMIT_Quality_data.html
https://github.com/nasa/EMIT-Data-Resources/blob/main/python/modules/emit_tools.py
https://lpdaac.usgs.gov/documents/1569/EMITL2ARFL_User_Guide_v1.pdf

L2A flags assess cloud/cirrus/water/spacecraft contamination. They do not rule
out surface spectral artifacts, thin clouds missed by the mask, or retrieval
errors. Passing this mask does not validate a methane plume.
"""

from __future__ import annotations

import re
from pathlib import Path

from affine import Affine
import h5netcdf
import numpy as np
import rasterio
from rasterio.crs import CRS

from .data import sha256, utc_now


DEFAULT_FLAGS = ("Cloud Flag", "Cirrus Flag", "Water Flag", "Spacecraft Flag", "Dilated Cloud Flag")
REFERENCE_URLS = [
    "https://nasa.github.io/LPDAAC-Data-Resources/external/How_to_use_EMIT_Quality_data.html",
    "https://github.com/nasa/EMIT-Data-Resources/blob/main/python/modules/emit_tools.py",
    "https://lpdaac.usgs.gov/documents/1569/EMITL2ARFL_User_Guide_v1.pdf",
]


def _text(value):
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def _label_key(value):
    return re.sub(r"[^a-z0-9]", "", _text(value).lower())


def _scene_key(path):
    found = re.search(r"_(\d{8}T\d{6})_(\d{7})_(\d{3})(?:\.|$)", Path(path).name)
    return found.groups() if found else None


def _gdal_transform(value):
    if isinstance(value, (str, bytes)):
        numbers = re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?", _text(value))
        values = np.array(numbers, dtype=float)
    else:
        values = np.asarray(value, dtype=float).ravel()
    if values.size != 6 or not np.isfinite(values).all():
        raise ValueError("Mask geotransform must contain six finite GDAL-order coefficients")
    result = Affine.from_gdal(*values)
    if abs(result.determinant) == 0:
        raise ValueError("Mask geotransform is singular")
    return result


def _window_to_target(source_transform, source_shape, source_crs, target_transform, target_shape, target_crs):
    """Return integer source window only when every target pixel coincides."""
    if CRS.from_user_input(source_crs) != CRS.from_user_input(target_crs):
        raise ValueError("Quality mask CRS differs from enhancement CRS")
    # The full pixel basis must agree; matching resolution alone is insufficient.
    source_basis = [source_transform.a, source_transform.b, source_transform.d, source_transform.e]
    target_basis = [target_transform.a, target_transform.b, target_transform.d, target_transform.e]
    if not np.allclose(source_basis, target_basis, rtol=0, atol=1e-12):
        raise ValueError("Quality mask and enhancement pixel grids require resampling")
    col_offset, row_offset = (~source_transform) * (target_transform.c, target_transform.f)
    if not np.allclose([col_offset, row_offset], np.rint([col_offset, row_offset]), rtol=0, atol=1e-6):
        raise ValueError("Quality mask and enhancement origins differ by a noninteger pixel offset")
    c0, r0 = int(round(col_offset)), int(round(row_offset))
    height, width = map(int, target_shape)
    if min(r0, c0) < 0 or r0 + height > source_shape[0] or c0 + width > source_shape[1]:
        raise ValueError("Enhancement grid extends outside the verified quality-mask GLT")
    return slice(r0, r0 + height), slice(c0, c0 + width)


def orthorectify_flags(mask, labels, glt_x, glt_y, *, flags=DEFAULT_FLAGS):
    """Map selected binary flags through an EMIT GLT, rejecting unknown values.

    Returns ``(usable, diagnostics)`` in the GLT grid. Nodata lookups, negative
    lookups, flag nodata, and any flag value outside {0,1} are unusable. Positive
    out-of-bounds lookups or fractional nonzero indices raise an error.
    """
    values = np.asarray(mask)
    labels = [_text(label) for label in labels]
    x, y = np.asarray(glt_x), np.asarray(glt_y)
    if values.ndim != 3 or values.shape[-1] != len(labels):
        raise ValueError("Mask cube must have downtrack,crosstrack,band dimensions matching labels")
    if x.ndim != 2 or y.shape != x.shape:
        raise ValueError("GLT x and y must be identically shaped two-dimensional arrays")
    label_lookup = {_label_key(label): i for i, label in enumerate(labels)}
    if len(label_lookup) != len(labels):
        raise ValueError("Quality flag labels must be unique")
    if not flags:
        raise ValueError("At least one explicit binary quality flag is required")
    missing = [label for label in flags if _label_key(label) not in label_lookup]
    if missing:
        raise ValueError(f"Required quality flags unavailable: {missing}")
    # Explicit allowlist prevents accidental thresholding of AOD/H2O data bands.
    binary_keys = {_label_key(label) for label in (*DEFAULT_FLAGS, "Aggregate Flag", "SpecTf Cloud Flag")}
    if any(_label_key(label) not in binary_keys for label in flags):
        raise ValueError("Only documented binary quality flags may be selected")
    finite = np.isfinite(x) & np.isfinite(y)
    nonzero = finite & (x != 0) & (y != 0)
    if np.any(nonzero & ((x != np.rint(x)) | (y != np.rint(y)))):
        raise ValueError("GLT indices must be integers")
    valid_glt = nonzero & (x > 0) & (y > 0)
    if np.any(valid_glt & ((x > values.shape[1]) | (y > values.shape[0]))):
        raise ValueError("GLT references pixels outside the raw mask dimensions")
    rr = y[valid_glt].astype(np.int64) - 1
    cc = x[valid_glt].astype(np.int64) - 1
    usable = valid_glt.copy()
    flag_counts = {}
    unknown_any = np.zeros(x.shape, dtype=bool)
    for label in flags:
        index = label_lookup[_label_key(label)]
        source = values[:, :, index]
        mapped = source[rr, cc]
        known = np.isfinite(mapped) & ((mapped == 0) | (mapped == 1))
        current_usable = np.zeros(x.shape, dtype=bool)
        current_usable[valid_glt] = known & (mapped == 0)
        usable &= current_usable
        current_unknown = np.zeros(x.shape, dtype=bool)
        current_unknown[valid_glt] = ~known
        unknown_any |= current_unknown
        flag_counts[labels[index]] = {
            "flagged_pixels": int(np.count_nonzero(known & (mapped == 1))),
            "unknown_pixels": int(np.count_nonzero(~known)),
        }
    return usable, {
        "selected_flags": list(flags), "available_flag_labels": labels,
        "glt_index_convention": "one-based x=sample/column, y=line/row; zero=nodata",
        "glt_shape": list(x.shape), "raw_mask_shape": list(values.shape),
        "valid_glt_pixels": int(valid_glt.sum()),
        "invalid_glt_pixels": int((~valid_glt).sum()),
        "unknown_quality_pixels": int(unknown_any.sum()),
        "usable_pixels": int(usable.sum()), "flag_counts_on_glt_grid": flag_counts,
        "usable_fraction_of_glt_footprint": float(usable.sum() / valid_glt.sum()) if valid_glt.any() else None,
    }


def quality_mask_for_enhancement(mask_path, enhancement_path, *, flags=DEFAULT_FLAGS):
    """Read an official EMIT MASK netCDF and return exact-grid usable pixels.

    Matching timestamp/orbit/scene identifiers are mandatory. Source mask GLT
    pixel basis, origin, CRS, and extent must exactly contain the target grid.
    If these checks fail, callers must report quality unavailable rather than
    silently applying an approximately geolocated mask.
    """
    mask_key, target_key = _scene_key(mask_path), _scene_key(enhancement_path)
    if mask_key is None or target_key is None or mask_key != target_key:
        raise ValueError("MASK and enhancement timestamp/orbit/scene identifiers do not match")
    with h5netcdf.File(mask_path, "r") as ds:
        if "mask" not in ds.variables or "location" not in ds.groups or "sensor_band_parameters" not in ds.groups:
            raise ValueError("Required EMIT MASK netCDF groups/variables unavailable")
        variable = ds.variables["mask"]
        dimensions = variable.dimensions
        if dimensions[:2] != ("downtrack", "crosstrack") or len(dimensions) != 3:
            raise ValueError("Unexpected EMIT mask cube dimension order")
        values = variable[:]
        loc = ds.groups["location"]
        if "glt_x" not in loc.variables or "glt_y" not in loc.variables:
            raise ValueError("EMIT MASK lacks GLT sample/line lookups")
        glt_x, glt_y = loc.variables["glt_x"][:], loc.variables["glt_y"][:]
        parameters = ds.groups["sensor_band_parameters"]
        if "mask_bands" not in parameters.variables:
            raise ValueError("EMIT MASK lacks named quality-band metadata")
        labels = parameters.variables["mask_bands"][:]
        if "geotransform" not in ds.attrs or "spatial_ref" not in ds.attrs:
            raise ValueError("EMIT MASK lacks explicit grid transform or spatial reference")
        source_transform = _gdal_transform(ds.attrs["geotransform"])
        source_crs = CRS.from_user_input(_text(ds.attrs["spatial_ref"]))
    usable, info = orthorectify_flags(values, labels, glt_x, glt_y, flags=flags)
    with rasterio.open(enhancement_path) as target:
        window = _window_to_target(source_transform, usable.shape, source_crs,
                                   target.transform, (target.height, target.width), target.crs)
        output = usable[window]
        target_footprint = (np.isfinite(glt_x) & np.isfinite(glt_y)
                            & (glt_x > 0) & (glt_y > 0))[window]
        footprint_pixels = int(target_footprint.sum())
        info.update({
            "mask_path": str(mask_path), "mask_sha256": sha256(mask_path),
            "enhancement_path": str(enhancement_path), "checked_at": utc_now(),
            "source_transform": list(source_transform)[:6],
            "target_transform": list(target.transform)[:6], "crs": str(target.crs),
            "target_shape": [target.height, target.width],
            "source_grid_window_rc": [window[0].start, window[1].start, window[0].stop, window[1].stop],
            "target_usable_pixels": int(output.sum()),
            "target_usable_fraction": float(output.mean()) if output.size else 0.,
            "target_glt_footprint_pixels": footprint_pixels,
            "target_usable_fraction_of_glt_footprint": float(output.sum() / footprint_pixels) if footprint_pixels else None,
            "mapping": "exact one-based GLT lookup plus integer grid window; no resampling",
            "source_references": REFERENCE_URLS,
            "limitations": [
                "L2A flags cannot rule out all cloud or surface spectral retrieval artifacts",
                "AOD and H2O continuous data bands are not treated as binary masks",
                "Per-wavelength interpolation band_mask is not evaluated here",
                "Passing quality flags does not independently confirm methane or a source",
            ],
        })
    return output, info
