"""Generate standalone scientific figures from frozen observed arrays."""
import json
import os
from pathlib import Path
import tempfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "methane-hunter-matplotlib"))
import numpy as np
from affine import Affine
from matplotlib import pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.ticker import MaxNLocator, FormatStrFormatter
from rasterio.features import geometry_mask
from shapely.geometry import shape, box

from methane_hunter.analysis import _catalog, _delta
from methane_hunter.data import aligned_rasters
from methane_hunter.detection import DetectionConfig, screen_enhancements
from methane_hunter.quality import quality_mask_for_enhancement
from methane_hunter.nasa_catalog import load_nasa_catalog
from dataclasses import replace

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/maps"


def plot_polygon(ax, geometry, **kwargs):
    for polygon in geometry.geoms if hasattr(geometry, "geoms") else [geometry]:
        x, y = polygon.exterior.xy
        ax.plot(x, y, **kwargs)


def raster_extent(meta, a):
    t = Affine(*meta["transform"])
    return [t.c, t.c + a.shape[1] * t.a, t.f + a.shape[0] * t.e, t.f]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    candidates = json.loads((ROOT / "outputs/candidates.json").read_text())
    manifest = json.loads((ROOT / "data/nasa_input_manifest.json").read_text())
    catalog = _catalog(ROOT)
    nasa = load_nasa_catalog(ROOT / "data/metadata/nasa_plume_cmr_same_scenes.json")
    cmap = plt.get_cmap("magma").copy()
    cmap.set_bad("#e7e7e7")
    colors = {"C": "#a45b09", "E": "#1689b5"}
    fig, axes = plt.subplots(4, 4, figsize=(16, 15), layout="constrained")
    figure_meta = []
    for i, c in enumerate(candidates):
        record = next(r for r in manifest if r["scene"]["name"] == c["scene_id"])
        files = record["files"]
        # Retain one scene in memory; the input order groups scene components.
        if i == 0 or candidates[i-1]["scene_id"] != c["scene_id"]:
            arrays, meta = aligned_rasters(ROOT / files["enhancement"]["path"], ROOT / files["sensitivity"]["path"], ROOT / files["uncertainty"]["path"])
            quality, _ = quality_mask_for_enhancement(ROOT / files["quality"]["path"], ROOT / files["enhancement"]["path"])
            with np.errstate(divide="ignore", invalid="ignore"):
                data = arrays["enhancement"] / arrays["sensitivity"]
            data[~quality | ~np.isfinite(data) | (arrays["sensitivity"] <= .1)] = np.nan
            data[~geometry_mask([box(-104.5,31,-102.5,33).__geo_interface__], out_shape=data.shape,
                                transform=Affine(*meta["transform"]), invert=True)] = np.nan
            extent = raster_extent(meta, data)
        ax = axes.flat[i]
        im = ax.imshow(data, extent=extent, cmap=cmap, origin="upper", interpolation="nearest", norm=Normalize(0, 3000))
        longitude, latitude = c["longitude"], c["latitude"]
        dx = 1500 / (111320 * np.cos(np.deg2rad(latitude)))
        dy = 1500 / 110900
        ax.set_xlim(longitude - dx, longitude + dx)
        ax.set_ylim(latitude - dy, latitude + dy)
        ax.set_aspect(1 / np.cos(np.deg2rad(latitude)))
        plot_polygon(ax, shape(c["geometry"]), color=colors[c["category"]], linewidth=1.3)
        for n in nasa:
            if _delta(c["observed_at"], n.observed_at) <= 120:
                plot_polygon(ax, n.geometry, color="#16a6c1", linewidth=.7, linestyle="--")
        for r in catalog:
            if _delta(c["observed_at"], r["scene_timestamp"]) <= 120:
                lon, lat = r["geometry_json"]["coordinates"]
                ax.scatter(lon, lat, marker="x", color="#16a6c1", s=30, linewidths=1)
        ax.tick_params(labelsize=8)
        ax.ticklabel_format(useOffset=False)
        ax.xaxis.set_major_locator(MaxNLocator(3))
        ax.yaxis.set_major_locator(MaxNLocator(4))
        ax.xaxis.set_major_formatter(FormatStrFormatter("%.3f"))
        ax.yaxis.set_major_formatter(FormatStrFormatter("%.3f"))
        ax.set_title(f"{c['candidate_id']} · {c['category']} · {c['observed_at'][:10]}\n{c['pixel_count']} pixels · peak {c['peak_ppm_m']:,.0f} ppm m", fontsize=10)
        figure_meta.append({"candidate_id": c["candidate_id"], "category": c["category"],
                            "half_width_m_approx": 1500, "figure_panel": i+1})
    for ax in list(axes.flat)[len(candidates):]:
        ax.axis("off")
    fig.colorbar(im, ax=list(axes.flat)[:len(candidates)], shrink=.6, label="Corrected enhancement (ppm m)", extend="max")
    fig.suptitle("All retained components · C = ambiguous; E = catalog associated\nBrown/blue solid: screened support · cyan cross/dashes: catalog head/outline · grey: excluded/nodata\nWGS84 longitude/latitude; 3 km neighborhood per panel; color scale clips values above 3,000 ppm m", fontsize=12)
    fig.savefig(OUT / "component_review.png", dpi=160)
    plt.close(fig)
    (OUT / "component_review.json").write_text(json.dumps(figure_meta, indent=2)+"\n")

    # First positive scene: a failed conservative screen with documented signal.
    record = manifest[0]
    files = record["files"]
    arrays, meta = aligned_rasters(ROOT / files["enhancement"]["path"], ROOT / files["sensitivity"]["path"], ROOT / files["uncertainty"]["path"])
    quality, _ = quality_mask_for_enhancement(ROOT / files["quality"]["path"], ROOT / files["enhancement"]["path"])
    arrays["enhancement"][~geometry_mask([box(-104.5,31,-102.5,33).__geo_interface__],
                            out_shape=arrays["enhancement"].shape,
                            transform=Affine(*meta["transform"]), invert=True)] = np.nan
    config = DetectionConfig()
    results = [screen_enhancements(arrays["enhancement"], sensitivity=arrays["sensitivity"], uncertainty=arrays["uncertainty"], quality_mask=quality, config=replace(config, background_sigma_multiplier=s, min_sensor_snr=s)) for s in [3., 5.]]
    fig, axes = plt.subplots(1, 2, figsize=(12, 6), layout="constrained")
    for ax, result, sigma in zip(axes, results, [3, 5]):
        extent = raster_extent(meta, result.corrected)
        im = ax.imshow(result.corrected, extent=extent, cmap=cmap, origin="upper", interpolation="nearest", norm=Normalize(0,3000))
        for n in nasa:
            if _delta(record["scene"]["timestamp"], n.observed_at) <= 120:
                plot_polygon(ax, n.geometry, color="#16a6c1", linewidth=1.1, linestyle="--")
        t = Affine(*meta["transform"])
        for c in result.candidates:
            x, y = t * (c.centroid_col+.5, c.centroid_row+.5)
            ax.scatter(x, y, facecolors="none", edgecolors="#a45b09", s=90, linewidths=1.5)
        ax.set_xlim(-103.97,-103.84)
        ax.set_ylim(31.71,31.79)
        ax.set_aspect(1 / np.cos(np.deg2rad(31.75)))
        ax.ticklabel_format(useOffset=False)
        ax.set_title(f"Multiplier {sigma}: {len(result.candidates)} components in scene/ROI", fontsize=12)
        ax.set_xlabel("Longitude (WGS84)")
        ax.set_ylabel("Latitude (WGS84)")
    fig.colorbar(im, ax=axes, shrink=.75, label="Corrected enhancement (ppm m)", extend="max")
    fig.suptitle("Known positive, 23 August 2024: threshold sensitivity\nCyan dashed = NASA plume outlines; circles = screened components; grey = quality excluded\nThe three-sigma diagnostic improves recovery; the unchanged five-sigma baseline misses these plumes.", fontsize=12)
    fig.savefig(OUT / "validation_thresholds.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
