# Frozen validation and execution protocol

Recorded 2026-10-19 (Europe/Vienna), before numeric screening of the frozen NASA full-scene sample. This is a prospective analysis contract; it does not assert that downloads, quality mapping, validation or search have succeeded.

## Sample and permitted inference

The controlling input is `data/metadata/nasa_selection.json`, SHA-256 `8058ddcdb9008eda3713e3bee6a4b4c78613e82d240f7de160345c10027ce36d`, retrieved `2026-10-18T21:50:51.934674+00:00`. Its twenty unique ENH V002 scene IDs are immutable for the baseline: two positive-validation scenes, two catalog-negative-control scenes and sixteen search scenes. Search coordinates are restricted to WGS84 longitude -104.5 to -102.5 and latitude 31 to 33; outside-ROI pixels may supply explicitly recorded processing context but cannot be reported as searched findings.

The selection began with Carbon Mapper EMIT scenes intersecting this box, Carbon Mapper cloud metadata <=25%, and acquisition dates through 2025-09-22. It is a convenience sample influenced by available catalog/provider coverage, not a random sample or all regional EMIT observations. Full-scene methane inputs are acquired from NASA. NASA and Carbon Mapper cloud estimates disagree, including NASA values substantially above 25%; assess official pixel quality rather than describing the sample as uniformly low-cloud. Consecutive granules in the same orbit segment are not independent emission events.

Positive-validation scene IDs:

- `EMIT_L2B_CH4ENH_002_20240823T173410_2423611_025`
- `EMIT_L2B_CH4ENH_002_20250323T212330_2508214_007`

Catalog-negative-control scene IDs:

- `EMIT_L2B_CH4ENH_002_20240216T201146_2404713_018`
- `EMIT_L2B_CH4ENH_002_20241004T165203_2427811_009`

The controls have zero published plumes in the saved Carbon Mapper scene metadata. This is a catalog condition, not verified absence of methane or a guarantee that every other provider has no detection. Recheck saved regional catalog rows for the control acquisition before final reporting and disclose the provider/time/coverage scope.

## Immutable baseline and ancillary conventions

Freeze `DetectionConfig` defaults from `src/methane_hunter/detection.py` and record them in every run manifest:

| Parameter | Baseline |
| --- | --- |
| Corrected enhancement floor | 500 ppm m |
| Local robust-background multiplier | 5 |
| Sensor-noise multiplier | 5 |
| Minimum component support | 4 pixels |
| Connectivity | 8-neighbor; no smoothing or mask growth |
| Sensitivity requirement | finite and strictly >0.1 |
| Background tile | 128 x 128 pixels |
| Minimum valid background support per tile | 32 pixels |
| Minimum background scale | 1 ppm m |
| Elongation flag | bounding-box aspect >=12 |
| Possible-stripe additional criteria | longest span >=20 pixels and >=0.5 of corresponding scene dimension |

Use corrected enhancement `E = CH4ENH / CH4SENS`. Use `CH4UNCERT` as supplied for the corrected convention. For valid pixels the baseline is `E >= max(500, b + 5*s, b + 5*CH4UNCERT)`, where `b` is the interpolated tile median and `s` the interpolated tile robust scale. The implemented robust scale is `max(1,1.4826*median(abs(E-median(E))))`; sparse tiles fall back to global valid-scene statistics. Local background includes valid negative enhancements. The sensor statistic is `(E-b)/CH4UNCERT`, not a calibrated probability of gas.

The convention was independently checked against actual NASA processing code: [diffmf.py at commit b8b4ccd8a05b0aa51f625657e0685983afaab88b, lines 573–598](https://github.com/emit-sds/emit-ghg/blob/b8b4ccd8a05b0aa51f625657e0685983afaab88b/emit_ghg/diffmf.py#L573-L598). It writes the raw matched-filter value, `SENS=sqrt(denom)/dtgt_norm`, and `UNCERT=sqrt(numer/denom)` with ppm scaling. The [deployment path, lines 180–240](https://github.com/emit-sds/emit-ghg/blob/b8b4ccd8a05b0aa51f625657e0685983afaab88b/deploy/ghg_process.py#L180-L240) georeferences and exports these quantities separately. Dividing UNCERT by sensitivity again would double-correct it. These are inspected current source revisions; retain each archived product's own processing metadata rather than claiming its exact build commit is known.

Apply official same-acquisition L2A MASK flags through its one-based sample/line GLT and an exact verified grid window. The initial flag allowlist is Cloud, Cirrus, Water, Spacecraft and Dilated Cloud. Do not threshold continuous AOD/H2O bands as flags. Any missing required flag, invalid lookup, unknown quality value, CRS/grid mismatch or ancillary misalignment makes affected quality unavailable/unusable; do not silently substitute approximate geolocation. Preserve finite valid enhancement/uncertainty/sensitivity support and exclude nodata. Passing masks does not rule out spectral surface confusers, missed thin clouds, shadows, interpolation artifacts or residual striping.

## Validation execution and gate

Run baseline positives and controls before interpreting search output. Report for each role: number attempted, downloaded, quality-mapped, analyzed and excluded, with reasons. Check pixel units, CRS/grid identity and quality exclusions before candidate generation. Record all positive misses and all control components. An unusable positive or control is a failed eligibility check, not a successful zero detection.

For each positive acquisition, identify the saved documented Carbon Mapper methane point(s) that actually fall within the ROI and valid observed footprint. Report the number eligible and matched. At least one defensible known-feature association in each of the two scenes is needed for the minimal positive-recovery gate. The denominator remains the exact number of eligible catalog features, with misses disclosed. Two positive scenes cannot support a global sensitivity estimate.

Control scenes require meaningful valid area and quality assessment, not just successful file opening. Report valid observed area and screening-component burden. Components in catalog-negative controls are **unexplained positive responses**, not measured false positives unless an alternative explanation is demonstrated. No universal specificity estimate can be computed from an incomplete catalog.

If either two-scene role cannot be assessed, the validation gate is incomplete. Exploratory bounded search may still be executed and documented to test pipeline behavior, but it cannot produce strong plume, completeness or novelty claims. Fixing an implementation error is permitted with an explicit log; a scientific threshold change requires a separate substantive iteration and retained baseline output.

## Documented-feature association

Use saved `carbonmapper_regional_plumes.json` with its exact query time, pagination status, per-feature ID, geometry, instrument and acquisition time. Distinguish a catalog point representing an estimated origin from a measured component centroid or maximum. Preserve provider fields rather than renaming them as truth.

The executed analysis path `analysis.polygon_catalog_matches` uses minimum distance from the catalog source point to the observed component polygon, with both projected to WGS84 / UTM zone 13N (EPSG:32613). Its fixed neighborhood tolerance is <=300 m, approximately five nominal EMIT pixels, and its acquisition-time tolerance is <=120 seconds. These are empirical, uncalibrated association choices rather than instrument-validated error bounds. The separate general-purpose `catalog.match_catalog` point-to-point default is not used for this run. An association outside time tolerance is only spatial context; a missing catalog time cannot establish a same-observation match. Scene/granule identity can strengthen temporal association but cannot relocate a catalog origin. Neighborhood agreement does not independently confirm methane, exact plume identity or source attribution.

A candidate near a documented source can be conservatively withheld from novelty consideration even when a source-to-polygon distance exceeds 300 m; a downwind gap, masking or catalog location error can break a true association. A successful nearby point match is an association, not proof that every pixel in the component is the cataloged plume. NASA outlines/source-scene relationships, if obtained, provide a more direct complex association. Do not declare a feature unmatched to all existing catalogs when only Carbon Mapper was queried or pagination was incomplete.

## Adversarial rules for every generated component

Keep a permanent candidate ID and a dossier containing observation/granule, raw/corrected measurements, support/geometry, units, background and sensor-noise statistics, quality flags, catalog matches and alternative explanations. Record what was checked and what was unavailable.

1. Test alignment, nodata leakage, image/quality boundaries and ROI clipping. Inspect highly elongated/scene-spanning components for striping. These flags trigger review; shape alone need not reject real gas.
2. Inspect cloud, cirrus, water, spacecraft and sensitivity context, including proximity to excluded pixels. Inspect RGB/radiance or surface context if available. Missing spectral/context evidence remains an explicit limitation.
3. Deduplicate adjacent-granule components and catalog overlaps by acquisition and geography. Repeated observations remain distinct measurement events but are not automatically separate sources.
4. Test a fixed secondary robustness setting, if resource permits: 3 and 7 robust-background/sensor multipliers with the same 500 ppm m floor and four-pixel support. Keep the baseline as the primary result. A sensitivity test cannot independently confirm gas, and it must not be tuned to maximize candidate novelty.
5. Examine repeat dates or another instrument when available. Fixed surface-pattern persistence is an alternative to persistent gas. Wind consistency requires observation-time wind information and uncertainty; shape alone is not a wind measurement.

Assign A only with independent observational corroboration; B only with affirmative artifact checks sufficient for credibility; C for unresolved/ambiguous responses; D only for a demonstrated rejection/explanation; E for documented observations. Category E documents association and does not independently verify the physical interpretation. If only automated masks/geometry checks are available, an unmatched high-valued component normally remains C. Store novelty independently as `previously_documented` or `not_established` unless a specifically documented broader prior-literature/catalog search supports a narrower novelty statement.

Do not infer a facility, source point or rate from a centroid. Leave these quantities unknown unless transport/high-resolution evidence and a justified quantitative method support them. No annualization is permitted.

## Plume-crop restriction

Public PLM exports are legitimate numeric products but do not replace full-scene validation controls. NASA's [delivery code at commit 6751936c9957af01ac7dc8db20b32ca8d1f45ed2](https://github.com/emit-sds/emit-sds-tgp/blob/6751936c9957af01ac7dc8db20b32ca8d1f45ed2/src/scrape_refine_upload.py#L539-L588) writes delivered COGs with a manually/algorithmically delineated plume mask. Pixels outside it become nodata via [write_cog](https://github.com/emit-sds/emit-sds-tgp/blob/6751936c9957af01ac7dc8db20b32ca8d1f45ed2/src/annotate/plume_io.py#L44-L85). Thresholding those selected pixels demonstrates reader/coordinate operation and selected-feature recovery only; treating them as unbiased background or independent detector validation would be circular.

## Audit and stopping rules

Save code/package versions, immutable sample/hash, actual downloaded bytes, source URLs without credentials, raw-response hashes, source-file hashes, executed parameters, role-wise metrics, candidate assessments and failed checks. Keep at most five substantive experiments and 5,000,000,000 downloaded bytes. Do not repeat a failed experiment without a recorded change/reason. Report the actual validated scope, including access or scientific blockers; no unknown emission is required for success.
