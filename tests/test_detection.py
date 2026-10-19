"""Synthetic fixtures verify software behavior, not observational validation."""

import numpy as np
import pytest

from methane_hunter.detection import DetectionConfig, screen_enhancements


def test_all_nodata_has_no_candidates_or_fabricated_statistics():
    result = screen_enhancements(np.full((12, 20), np.nan))
    assert result.candidates == []
    assert not result.valid.any()
    assert np.isnan(result.threshold).all()
    assert result.diagnostics["global_background_median_ppm_m"] is None


def test_constant_and_single_spike_fields_are_not_components():
    data = np.zeros((50, 50))
    data[25, 25] = 10000
    assert not screen_enhancements(np.zeros((50, 50))).candidates
    result = screen_enhancements(data)
    assert not result.candidates
    assert not result.labels.any()


def test_sensitivity_correction_and_sensor_uncertainty_convention():
    data = np.zeros((30, 30))
    data[12:15, 12:15] = 300
    sensitivity = np.full(data.shape, 0.5)
    uncertainty = np.full(data.shape, 110.)
    result = screen_enhancements(data, sensitivity=sensitivity, uncertainty=uncertainty,
                                quality_mask=np.ones(data.shape, dtype=bool))
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.peak_ppm_m == 600.
    assert candidate.pixel_count == 9
    assert candidate.median_sensor_snr == pytest.approx(600 / 110)
    assert candidate.flags == ()
    # Double-correcting 110 to 220 would wrongly suppress this fixture.
    assert result.threshold[13, 13] == 550.


def test_invalid_quality_and_dim_sensitivity_pixels_are_excluded():
    data = np.zeros((30, 30))
    data[12:15, 12:15] = 900
    quality = np.ones_like(data, dtype=bool)
    quality[12:15, 12:15] = False
    assert not screen_enhancements(data, quality_mask=quality).candidates
    sensitivity = np.ones_like(data)
    sensitivity[12:15, 12:15] = 0.01
    assert not screen_enhancements(data, sensitivity=sensitivity).candidates


def test_missing_uncertainty_is_explicit_and_does_not_become_zero():
    data = np.zeros((30, 30))
    data[12:15, 12:15] = 900
    result = screen_enhancements(data)
    assert result.candidates[0].median_sensor_snr is None
    assert "sensor_uncertainty_unavailable" in result.candidates[0].flags
    assert result.diagnostics["sensor_uncertainty_available"] is False


def test_connected_diagonal_pixels_use_eight_connectivity():
    data = np.zeros((30, 30))
    np.fill_diagonal(data[12:16, 12:16], 900)
    result = screen_enhancements(data)
    assert len(result.candidates) == 1
    assert result.candidates[0].pixel_count == 4


def test_long_stripe_is_flagged_for_review():
    data = np.zeros((100, 100))
    data[:, 50] = 900
    result = screen_enhancements(data)
    assert len(result.candidates) == 1
    assert "possible_image_stripe" in result.candidates[0].flags
    assert "touches_raster_edge" in result.candidates[0].flags


def test_invalid_footprint_edge_is_flagged():
    data = np.zeros((30, 30))
    data[12:15, 12:15] = 900
    data[11, 12:15] = np.nan
    result = screen_enhancements(data)
    assert "touches_invalid_pixels" in result.candidates[0].flags


@pytest.mark.parametrize("argument", ["sensitivity", "uncertainty", "quality_mask"])
def test_misaligned_raster_shapes_are_rejected(argument):
    with pytest.raises(ValueError, match="shape"):
        screen_enhancements(np.zeros((20, 20)), **{argument: np.ones((20, 19))})


def test_sensor_noise_can_suppress_high_enhancement():
    data = np.zeros((30, 30))
    data[12:15, 12:15] = 900
    result = screen_enhancements(data, uncertainty=np.full(data.shape, 200.))
    assert not result.candidates


def test_local_robust_background_handles_spatial_shift():
    data = np.zeros((64, 128))
    data[:, 64:] = 200.
    result = screen_enhancements(data, config=DetectionConfig(background_tile_pixels=32))
    assert not result.candidates
    assert result.background[32, 110] == pytest.approx(200.)
    assert result.background[32, 10] == pytest.approx(0.)


def test_invalid_config_is_rejected():
    with pytest.raises(ValueError):
        DetectionConfig(min_pixels=0)
    with pytest.raises(ValueError):
        DetectionConfig(background_sigma_multiplier=float("nan"))
