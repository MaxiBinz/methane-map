"""Synthetic TIFF fixtures test acquisition packaging, never methane validation."""

import json

import numpy as np
import pytest
import rasterio
from rasterio.enums import ColorInterp
from rasterio.transform import from_origin

from methane_hunter.public_data import native_export_request, validate_public_export, fetch_public_selected


ITEM = "EMIT_L2B_CH4PLM_002_20241130T180310_003725"
AFFINE = from_origin(-103., 32., .001, .001)


def write_tiff(path, *, shape=(8, 10), dtype="float32", alpha=False, alpha_interp=True):
    data = np.full(shape, 123., dtype=dtype)
    with rasterio.open(path, "w", driver="GTiff", height=shape[0], width=shape[1],
                       count=2 if alpha else 1, dtype=dtype, crs="EPSG:4326",
                       transform=AFFINE, nodata=None if alpha else -9999) as ds:
        ds.write(data, 1)
        if alpha:
            mask = np.zeros(shape, dtype=dtype)
            mask[3:5, 4:7] = 255
            ds.write(mask, 2)
            if alpha_interp:
                ds.colorinterp = (ColorInterp.gray, ColorInterp.alpha)
    return {"shape": list(shape), "bounds": [-103., 32. - shape[0] * .001, -103. + shape[1] * .001, 32.],
            "transform": list(AFFINE), "epsg": 4326}


def test_native_export_has_no_color_or_rescale_operations():
    endpoint, params = native_export_request(ITEM, 2048, 1250)
    assert endpoint.endswith("/" + ITEM + "/preview.tif")
    assert params["width"] == 2048 and params["height"] == 1250
    assert params["max_size"] == 2048
    assert params["resampling"] == "nearest"
    assert "rescale" not in params and "colormap_name" not in params


def test_alpha_mask_support_is_measured_without_zero_filling(tmp_path):
    path = tmp_path / "alpha.tif"
    grid = write_tiff(path, alpha=True)
    result = validate_public_export(path, grid)
    assert result["valid_pixels"] == 6
    assert result["total_pixels"] == 80
    assert result["maximum_ppm_m"] == 123.
    assert result["valid_fraction"] == 6 / 80


def test_dimension_mismatch_and_unidentified_extra_band_fail_closed(tmp_path):
    path = tmp_path / "data.tif"
    grid = write_tiff(path)
    grid["shape"] = [8, 11]
    with pytest.raises(ValueError, match="dimensions"):
        validate_public_export(path, grid)
    path2 = tmp_path / "ambiguous.tif"
    grid2 = write_tiff(path2, alpha=True, alpha_interp=False)
    with pytest.raises(ValueError, match="alpha"):
        validate_public_export(path2, grid2)


def test_rendered_byte_image_is_rejected(tmp_path):
    path = tmp_path / "rendered.tif"
    grid = write_tiff(path, dtype="uint8", alpha=True)
    with pytest.raises(ValueError, match="floating-point"):
        validate_public_export(path, grid)


def test_shifted_source_grid_is_rejected(tmp_path):
    path = tmp_path / "data.tif"
    grid = write_tiff(path)
    grid["bounds"][0] += .001
    with pytest.raises(ValueError, match="bounds"):
        validate_public_export(path, grid)


def test_item_validation_rejects_path_injection():
    with pytest.raises(ValueError, match="identifier"):
        native_export_request("../secret", 10, 10)


def test_initial_sample_limit_checked_before_network(tmp_path):
    path = tmp_path / "selection.json"
    path.write_text(json.dumps({"scenes": [{"name": ITEM}] * 21}))
    with pytest.raises(ValueError, match="20"):
        fetch_public_selected(tmp_path, selection_path=path)
