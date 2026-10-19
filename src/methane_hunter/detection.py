"""Conservative screening of observed EMIT enhancement rasters.

This is a hypothesis generator, not a validated methane-plume classifier. It
cannot check spectra, surface reflectance, clouds, or wind by itself. Thresholds
are exploratory parameters and must be validated on real positive and control
scenes before interpreting unmatched components as methane.

EMIT V002 enhancement is divided by sensitivity when supplied. ``uncertainty``
must already use the sensitivity-corrected enhancement convention: the V002
sensor-noise uncertainty must not automatically be divided by sensitivity a
second time. Sensor uncertainty does not include all surface-clutter errors.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import numpy as np
from scipy import ndimage


@dataclass(frozen=True)
class DetectionConfig:
    """Explicit screening parameters; enhancement values have units ppm m."""

    min_enhancement_ppm_m: float = 500.0
    background_sigma_multiplier: float = 5.0
    min_sensor_snr: float = 5.0
    min_pixels: int = 4
    min_sensitivity: float = 0.1
    background_tile_pixels: int = 128
    min_background_pixels: int = 32
    min_background_scale_ppm_m: float = 1.0
    stripe_aspect_ratio: float = 12.0
    stripe_min_length_pixels: int = 20
    stripe_scene_fraction: float = 0.5

    def __post_init__(self):
        for key in (
            "min_enhancement_ppm_m", "background_sigma_multiplier",
            "min_sensor_snr", "min_sensitivity", "min_background_scale_ppm_m",
            "stripe_aspect_ratio",
        ):
            value = getattr(self, key)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{key} must be positive and finite")
        for key in ("min_pixels", "background_tile_pixels", "min_background_pixels", "stripe_min_length_pixels"):
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{key} must be a positive integer")
        if not 0 < self.stripe_scene_fraction <= 1:
            raise ValueError("stripe_scene_fraction must be in (0, 1]")


@dataclass(frozen=True)
class Candidate:
    label: int
    pixel_count: int
    centroid_row: float
    centroid_col: float
    peak_row: int
    peak_col: int
    bbox_rc: tuple[int, int, int, int]
    peak_ppm_m: float
    mean_ppm_m: float
    median_ppm_m: float
    median_excess_ppm_m: float
    median_sensor_snr: float | None
    flags: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DetectionResult:
    corrected: np.ndarray
    valid: np.ndarray
    background: np.ndarray
    background_scale: np.ndarray
    threshold: np.ndarray
    labels: np.ndarray
    candidates: list[Candidate]
    diagnostics: dict


def _array(value, name: str, shape: tuple[int, int] | None = None) -> np.ndarray:
    array = np.asarray(value)
    if array.ndim != 2:
        raise ValueError(f"{name} must be a two-dimensional raster")
    if shape is not None and array.shape != shape:
        raise ValueError(f"{name} shape {array.shape} does not match enhancement {shape}")
    return array


def _robust(values: np.ndarray, scale_floor: float) -> tuple[float, float]:
    median = float(np.median(values))
    sigma = max(float(1.4826 * np.median(np.abs(values - median))), scale_floor)
    return median, sigma


def _background_fields(values: np.ndarray, valid: np.ndarray, config: DetectionConfig):
    """Interpolate robust tile medians/MADs, falling back to scene statistics.

    Tile statistics keep full-scene CPU/memory costs bounded. Their interpolated
    scale is an empirical background diagnostic, not a formal Gaussian error
    model or a calibrated false-alarm probability.
    """
    global_median, global_scale = _robust(values[valid], config.min_background_scale_ppm_m)
    height, width = values.shape
    tile = config.background_tile_pixels
    rows = math.ceil(height / tile)
    cols = math.ceil(width / tile)
    medians = np.full((rows, cols), global_median, dtype=np.float64)
    scales = np.full((rows, cols), global_scale, dtype=np.float64)
    for row in range(rows):
        for col in range(cols):
            slices = (slice(row * tile, min((row + 1) * tile, height)),
                      slice(col * tile, min((col + 1) * tile, width)))
            local = values[slices][valid[slices]]
            if local.size >= config.min_background_pixels:
                medians[row, col], scales[row, col] = _robust(local, config.min_background_scale_ppm_m)
    # Interpolate at tile centers; extrapolation outside centers is nearest.
    yy, xx = np.meshgrid((np.arange(height) + 0.5) / tile - 0.5,
                         (np.arange(width) + 0.5) / tile - 0.5, indexing="ij")
    background = ndimage.map_coordinates(medians, [yy, xx], order=1, mode="nearest")
    scale = ndimage.map_coordinates(scales, [yy, xx], order=1, mode="nearest")
    return background, scale, global_median, global_scale


def screen_enhancements(
    enhancement,
    *,
    sensitivity=None,
    uncertainty=None,
    quality_mask=None,
    config: DetectionConfig | None = None,
) -> DetectionResult:
    """Find connected high-enhancement components in a co-registered raster.

    ``quality_mask=True`` means usable. Nodata must be converted to NaN or
    excluded in that mask before calling. Optional arrays must have exactly the
    same shape; geospatial transforms/CRSs must be checked by the caller.
    Uncertainty is a *sensor-noise* standard deviation in corrected ppm m.
    Missing ancillary arrays are recorded explicitly and never filled by zero.

    A pixel must exceed the absolute floor and local background by the greater
    of the empirical robust-background and sensor-noise thresholds. Four-neighbor
    or eight-neighbor morphology is not proof of a physical plume; this uses
    eight-neighbor connectivity without smoothing or growing the observations.
    """
    config = config or DetectionConfig()
    raw = _array(enhancement, "enhancement").astype(np.float64, copy=True)
    valid = np.isfinite(raw)
    if quality_mask is not None:
        valid &= _array(quality_mask, "quality_mask", raw.shape).astype(bool)
    corrected = np.full(raw.shape, np.nan)
    if sensitivity is not None:
        sens = _array(sensitivity, "sensitivity", raw.shape).astype(np.float64)
        valid &= np.isfinite(sens) & (sens > config.min_sensitivity)
        np.divide(raw, sens, out=corrected, where=valid)
    else:
        corrected[valid] = raw[valid]
    unc = None
    if uncertainty is not None:
        unc = _array(uncertainty, "uncertainty", raw.shape).astype(np.float64)
        valid &= np.isfinite(unc) & (unc > 0)
    corrected[~valid] = np.nan
    shape = raw.shape
    diagnostics = {
        "method": "robust_tile_background_connected_components_v1",
        "interpretation": "exploratory enhancement screen; not independently verified methane",
        "config": asdict(config),
        "valid_pixels": int(valid.sum()),
        "total_pixels": int(raw.size),
        "valid_fraction": float(valid.mean()) if raw.size else 0.0,
        "sensitivity_available": sensitivity is not None,
        "sensor_uncertainty_available": unc is not None,
        "cloud_or_surface_quality_mask_available": quality_mask is not None,
        "global_background_median_ppm_m": None,
        "global_background_scale_ppm_m": None,
        "supra_threshold_pixels": 0,
        "components_before_min_pixels": 0,
    }
    if not valid.any():
        missing = np.full(shape, np.nan)
        return DetectionResult(corrected, valid, missing.copy(), missing.copy(),
                               missing.copy(), np.zeros(shape, dtype=np.int32), [], diagnostics)
    background, scale, median, global_scale = _background_fields(corrected, valid, config)
    diagnostics["global_background_median_ppm_m"] = median
    diagnostics["global_background_scale_ppm_m"] = global_scale
    threshold = np.maximum(config.min_enhancement_ppm_m,
                           background + config.background_sigma_multiplier * scale)
    if unc is not None:
        threshold = np.maximum(threshold, background + config.min_sensor_snr * unc)
    threshold[~valid] = np.nan
    selected = valid & (corrected >= threshold)
    labels, count = ndimage.label(selected, structure=np.ones((3, 3), dtype=np.uint8))
    diagnostics["supra_threshold_pixels"] = int(selected.sum())
    diagnostics["components_before_min_pixels"] = int(count)
    candidates = []
    height, width = shape
    for label, slices in enumerate(ndimage.find_objects(labels), start=1):
        if slices is None:
            continue
        local_mask = labels[slices] == label
        count_pixels = int(local_mask.sum())
        if count_pixels < config.min_pixels:
            labels[slices][local_mask] = 0
            continue
        rr, cc = np.nonzero(local_mask)
        rr += slices[0].start
        cc += slices[1].start
        values = corrected[rr, cc]
        peak_index = int(np.argmax(values))
        r0, r1 = slices[0].start, slices[0].stop
        c0, c1 = slices[1].start, slices[1].stop
        flags = []
        if sensitivity is None:
            flags.append("sensitivity_correction_unavailable")
        if unc is None:
            flags.append("sensor_uncertainty_unavailable")
        if quality_mask is None:
            flags.append("cloud_surface_quality_unassessed")
        if r0 == 0 or c0 == 0 or r1 == height or c1 == width:
            flags.append("touches_raster_edge")
        # Also flag edges in rotated footprints and holes from quality masks.
        expanded_slices = (slice(max(r0 - 1, 0), min(r1 + 1, height)),
                           slice(max(c0 - 1, 0), min(c1 + 1, width)))
        expanded_mask = labels[expanded_slices] == label
        if np.any(ndimage.binary_dilation(expanded_mask) & ~valid[expanded_slices]):
            flags.append("touches_invalid_pixels")
        span_r, span_c = r1 - r0, c1 - c0
        aspect = max(span_r, span_c) / max(min(span_r, span_c), 1)
        if aspect >= config.stripe_aspect_ratio:
            flags.append("highly_elongated_component")
            scene_span = height if span_r >= span_c else width
            if (max(span_r, span_c) >= config.stripe_min_length_pixels
                    and max(span_r, span_c) / max(scene_span, 1) >= config.stripe_scene_fraction):
                flags.append("possible_image_stripe")
        if count_pixels > valid.sum() * 0.1:
            flags.append("large_scene_fraction")
        excess = values - background[rr, cc]
        candidates.append(Candidate(
            label=label, pixel_count=count_pixels,
            centroid_row=float(rr.mean()), centroid_col=float(cc.mean()),
            peak_row=int(rr[peak_index]), peak_col=int(cc[peak_index]),
            bbox_rc=(r0, c0, r1, c1), peak_ppm_m=float(values.max()),
            mean_ppm_m=float(values.mean()), median_ppm_m=float(np.median(values)),
            median_excess_ppm_m=float(np.median(excess)),
            median_sensor_snr=float(np.median(excess / unc[rr, cc])) if unc is not None else None,
            flags=tuple(flags),
        ))
    diagnostics["retained_components"] = len(candidates)
    return DetectionResult(corrected, valid, background, scale, threshold, labels, candidates, diagnostics)
