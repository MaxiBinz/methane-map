"""Synthetic quality flags and GLTs test software alignment, not real clouds."""

import h5netcdf
import numpy as np
import pytest
import rasterio
from affine import Affine
from rasterio.transform import from_origin

from methane_hunter.quality import DEFAULT_FLAGS, orthorectify_flags, quality_mask_for_enhancement


def base_fixture():
    cube = np.zeros((3, 4, 5), dtype=np.float32)
    xx, yy = np.meshgrid(np.arange(1, 5), np.arange(1, 4))
    return cube, xx, yy


def test_one_based_lookup_respects_sample_line_order_and_nodata():
    cube, xx, yy = base_fixture()
    cube[1, 2, 0] = 1
    xx[0, 0] = 0
    result, info = orthorectify_flags(cube, DEFAULT_FLAGS, xx, yy)
    assert result.shape == (3, 4)
    assert not result[1, 2] and not result[0, 0]
    assert result.sum() == 10
    assert info["flag_counts_on_glt_grid"]["Cloud Flag"]["flagged_pixels"] == 1
    assert xx[1, 2] == 3  # input GLTs are never decremented in place


def test_unknown_values_and_nodata_are_unusable():
    cube, xx, yy = base_fixture()
    cube[0, 0, 0] = -9999
    cube[0, 1, 1] = np.nan
    cube[0, 2, 2] = 0.5
    result, info = orthorectify_flags(cube, DEFAULT_FLAGS, xx, yy)
    assert not result[0, :3].any()
    assert result.sum() == 9
    assert info["unknown_quality_pixels"] == 3


def test_fractional_and_out_of_bounds_glt_indices_fail_closed():
    cube, xx, yy = base_fixture()
    bad = xx.astype(float)
    bad[0, 0] = 1.5
    with pytest.raises(ValueError, match="integers"):
        orthorectify_flags(cube, DEFAULT_FLAGS, bad, yy)
    xx[0, 0] = 5
    with pytest.raises(ValueError, match="outside"):
        orthorectify_flags(cube, DEFAULT_FLAGS, xx, yy)


def test_missing_flags_and_continuous_data_bands_are_rejected():
    cube, xx, yy = base_fixture()
    with pytest.raises(ValueError, match="unavailable"):
        orthorectify_flags(cube, ["AOD550", *DEFAULT_FLAGS[1:]], xx, yy)
    with pytest.raises(ValueError, match="binary"):
        orthorectify_flags(cube, ["AOD550", *DEFAULT_FLAGS[1:]], xx, yy, flags=("AOD550",))


def write_mask_and_target(tmp_path, *, target_transform=None, target_shape=(3, 4), mismatch=False):
    mask = tmp_path / "EMIT_L2A_MASK_001_20241130T180310_2433512_003.nc"
    target = tmp_path / ("EMIT_L2B_CH4ENH_002_20241130T180311_2433512_003.tif" if mismatch
                         else "EMIT_L2B_CH4ENH_002_20241130T180310_2433512_003.tif")
    cube, xx, yy = base_fixture()
    cube[1, 2, 0] = 1
    transform = from_origin(-103., 32., .001, .001)
    with h5netcdf.File(mask, "w") as ds:
        ds.dimensions = {"downtrack": 3, "crosstrack": 4, "bands": 5, "ortho_y": 3, "ortho_x": 4}
        ds.create_variable("mask", ("downtrack", "crosstrack", "bands"), data=cube)
        ds.attrs["geotransform"] = transform.to_gdal()
        ds.attrs["spatial_ref"] = rasterio.crs.CRS.from_epsg(4326).to_wkt()
        loc = ds.create_group("location")
        loc.create_variable("glt_x", ("ortho_y", "ortho_x"), data=xx)
        loc.create_variable("glt_y", ("ortho_y", "ortho_x"), data=yy)
        parameters = ds.create_group("sensor_band_parameters")
        parameters.create_variable("mask_bands", ("bands",), data=np.asarray(DEFAULT_FLAGS, dtype="S30"))
    with rasterio.open(target, "w", driver="GTiff", height=target_shape[0], width=target_shape[1],
                       count=1, dtype="float32", crs="EPSG:4326", transform=target_transform or transform) as ds:
        ds.write(np.zeros(target_shape, dtype="float32"), 1)
    return mask, target


def test_netcdf_reader_exact_alignment_and_mask_values(tmp_path):
    mask, target = write_mask_and_target(tmp_path)
    result, info = quality_mask_for_enhancement(mask, target)
    assert result.dtype == bool and result.shape == (3, 4)
    assert result.sum() == 11 and not result[1, 2]
    assert info["source_grid_window_rc"] == [0, 0, 3, 4]
    assert len(info["mask_sha256"]) == 64


def test_exact_integer_subwindow_is_allowed(tmp_path):
    transform = from_origin(-103., 32., .001, .001) * Affine.translation(1, 1)
    mask, target = write_mask_and_target(tmp_path, target_transform=transform, target_shape=(2, 3))
    result, info = quality_mask_for_enhancement(mask, target)
    assert result.shape == (2, 3) and result.sum() == 5
    assert not result[0, 1]
    assert info["source_grid_window_rc"] == [1, 1, 3, 4]


def test_fractional_pixel_shift_is_not_approximated(tmp_path):
    transform = from_origin(-103., 32., .001, .001) * Affine.translation(.5, 0)
    mask, target = write_mask_and_target(tmp_path, target_transform=transform)
    with pytest.raises(ValueError, match="noninteger"):
        quality_mask_for_enhancement(mask, target)


def test_different_scene_identity_is_rejected(tmp_path):
    mask, target = write_mask_and_target(tmp_path, mismatch=True)
    with pytest.raises(ValueError, match="identifiers"):
        quality_mask_for_enhancement(mask, target)
