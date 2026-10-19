# Validation report: operational pipeline, incomplete detection validation

Analysis completed 19 October 2026. The baseline numerical pipeline ran successfully on twenty full NASA EMIT enhancement granules, but its planned detection-validation gate was not met. It failed to associate any retained component with the documented neighborhoods in the first positive scene and recovered only one of ten catalog source heads in the second at the primary 300 m tolerance. These are sample-specific neighborhood-recovery results, not estimates of global detection sensitivity.

## What was tested

The frozen sample has two positive-validation, two catalog-negative-control and sixteen search granules, clipped to WGS84 [-104.5,31,-102.5,33]. They span sixteen dates between 2023-12-24 and 2025-09-22. Selection used provider scene coverage and cloud metadata; it is neither random nor a complete regional archive. NASA and Carbon Mapper cloud metadata disagree, so selection metadata did not substitute for pixel quality.

Inputs were NASA CH4ENH, CH4SENS, CH4UNCERT V002 and matching official L2A MASK files. ENH was divided by sensitivity; supplied UNCERT was left unchanged because NASA's processing expression already uses the sensitivity-corrected convention. Five named binary quality flags were mapped with the official one-based GLT and exact grid-window checks. All twenty scenes passed those alignment checks. This checks processing consistency; it does not independently validate atmospheric methane.

The immutable baseline retained eight-connected groups of at least four pixels above max(500 ppm m, local median + 5 robust sigma, local median + 5 sensor uncertainty), with sensitivity>0.1. Tile size was 128 pixels, minimum background support 32 and minimum background scale 1 ppm m. No smoothing or mask growth was used. Negative valid enhancement values were retained for background statistics. Sensor uncertainty excludes important surface/clutter errors, and the resulting statistic is not a calibrated discovery probability.

## Known-example and control outcomes

| Observation (UTC) | Frozen role | Usable pixel-observations | In-ROI catalog source heads | Heads associated at baseline | Retained components |
| --- | --- | ---: | ---: | ---: | ---: |
|2024-08-23T17:34:10Z|Positive|1,548,205|4|0|0|
|2025-03-23T21:23:30Z|Positive|3,192,343|10|1|10|
|2024-02-16T20:11:46Z|Catalog-negative control|559,665|0|0|0|
|2024-10-04T16:52:03Z|Catalog-negative control|12,419|0|0|0|

Two retained components in the second positive scene associated with the same catalog source neighborhood; one recovered source head does not mean two recovered physical sources. The reference-head pixel usability diagnostics mark two of the first scene's four heads unusable and the other two usable; all ten heads in the second scene are usable. Head usability is context, because a real plume can extend downwind. The table's source-head denominators retain all in-ROI references rather than hiding quality-related misses.

The control scenes provide 572,084 usable pixel-observations, with very unequal support between the two scenes. Zero retained components is an observed screen result. It neither proves methane absence nor estimates specificity against independent ground truth.

## Fixed threshold diagnostics explain part of the failure

The separate E02 diagnostic kept the baseline unchanged and applied the already specified three-, five- and seven-times criteria. Its 300 m source-head and NASA outline checks found:

| Positive acquisition | Multiplier | Carbon Mapper heads associated | NASA outlines intersected |
| --- | ---: | ---: | ---: |
|2024-08-23T17:34:10Z|3|2/4|2/3|
|2024-08-23T17:34:10Z|5|0/4|0/3|
|2024-08-23T17:34:10Z|7|0/4|0/3|
|2025-03-23T21:23:30Z|3|7/10|0/0; unavailable in this exact-time query|
|2025-03-23T21:23:30Z|5|1/10|0/0; unavailable in this exact-time query|
|2025-03-23T21:23:30Z|7|0/10|0/0; unavailable in this exact-time query|

The empty NASA exact-start-time result for March 2025 is catalog/query coverage, not evidence that no methane existed or that Carbon Mapper was wrong. PLM products can span scenes and use the earliest scene's timestamp; exact-time queries can miss a valid relationship. NASA and Carbon Mapper also use different retrieval/masking/catalog conventions on the same photons. Neither is independent atmospheric corroboration of the other.

For some known neighborhoods, cloud-buffer exclusion removed signal; other misses reflected the sensor-noise criterion or a failure to retain four connected pixels. Enlarging the point neighborhood to 1 km changed some associations, illustrating source-head displacement and tolerance dependence. These diagnostics identify method limitations. They do not justify post hoc threshold selection, establish independent methane truth or validate unmatched components.

## Bounded search and initial candidate assessments

Across all twenty granules, 15,917,415 usable pixel-observations produced fourteen baseline components: six E and eight C. The sixteen frozen search granules produced four components, all Category E. All eight C components were in the second positive-validation scene. No A or B category was assigned, and no genuinely new source was established.

The association rule measures the minimum source-point-to-component-polygon distance in EPSG:32613 with an empirical 300 m tolerance and an acquisition-time difference of at most 120 seconds. A Category E label is a documented-observation neighborhood association, not independent confirmation or exact plume/source identity. Per-scene queries include cataloged source heads outside the region. Finite archive coverage and empirical spatial/time tolerances can still cause missed associations. Unmatched components remain hypotheses.

Initial adversarial checks include official quality/sensitivity support, boundary/nodata proximity, component elongation, local annulus contrast and catalog association. Dossiers explicitly retain untested spectral fits, surface reflectance, wind consistency and another sensor. Re-thresholding the same raster is only a robustness check. The completed candidate audit is retained with each unresolved alternative; it did not upgrade any category.

## Separate adversarial and visual review

All fourteen components underwent the reproducible review in `outputs/adversarial_audit.json`, plus assistant visual inspection of all fourteen actual numeric-data panels recorded in `outputs/visual_review.json` and `reports/component_visual_review.md`. The structural/time/ROI/provenance consistency checks passed for every component. These are processing checks, not independent spectral or atmospheric validation. No category changed.

- Two potential same-event fragment pairs were identified: `MH-02-0020`/`MH-02-0021` and `MH-02-0097`/`MH-02-0098`. They were not automatically merged into physical sources.
- Two C components lie between 300 m and 1 km from a same-acquisition catalog source. `MH-02-0064` is about 920 m away and has a local-annulus contrast of 2.82 robust-sigma units; `MH-02-0075` is about 651 m away. Previously cataloged plume extensions remain an alternative to a separate emission.
- Six components lie within 1.5 km of excluded-quality pixel centers. A direct recheck found zero excluded pixels inside retained component support. Proximity is approximate at half-pixel scale and does not establish contamination.
- No cross-granule potential duplicate pair or cross-date component-neighborhood recurrence was found within the tested sample. One component has other-date catalog context within 1 km. These finite-sample comparisons do not establish source transience, persistence or novelty.

The visual review described compact unresolved clusters, elongated features and threshold fragmentation. Independent radiance fitting, surface/mineral comparison, wind consistency and another sensor remained unchecked. Categories stayed six E / eight C, with no A or B evidence and no new-source conclusion.

Figures: [all-component review](../outputs/maps/component_review.png) and [first-positive threshold comparison](../outputs/maps/validation_thresholds.png). Both derive from the same EMIT retrievals and are not independent sensor corroboration.


## Reproducibility and evidence scope

- Frozen selection and baseline: `data/metadata/nasa_selection.json`, `outputs/run_parameters.json` and `research/validation_protocol.md`.
- Numeric inputs, URLs, hashes and bytes: `data/nasa_input_manifest.json` and download ledgers.
- Exact quality mapping: per-scene JSON in `outputs/quality/`.
- Metrics and findings: `outputs/scene_metrics.csv`, `outputs/candidates.csv`, `outputs/candidates.geojson` and `outputs/dossiers/`.
- Known-example diagnostics: `outputs/known_diagnostics.json`, whose source hashes and command are recorded inside it.
- Maps: `outputs/maps/scene_01.png` through `scene_20.png`.

The complete E05 local replay reproduced all twenty scene-metric records and the fourteen components’ compared numeric, geometric and category fields exactly (`outputs/reproducibility.json`). The recorded essential test suite passed **56 tests; 0 failures, 0 errors and 0 skips** (`outputs/test_results.xml`). All 80 frozen NASA input files were checked by the analysis before processing; the input manifest records their hashes. Repeating one implementation on identical inputs does not provide an independent physical test.

The successful run establishes reproducible file reading, co-registration, masking, screening and bounded catalog comparison. Software checks do not substitute for physical validation. The two-scene positive gate remains incomplete, so this package cannot support strong discovery claims or a conclusion that regional catalogs are comprehensive. No emission rates, annual totals or facility responsibility were estimated.

Primary methodological references: [NASA EMIT V002 product](https://doi.org/10.5067/EMIT/EMITL2BCH4ENH.002), [actual NASA uncertainty implementation](https://github.com/emit-sds/emit-ghg/blob/b8b4ccd8a05b0aa51f625657e0685983afaab88b/emit_ghg/diffmf.py#L573-L598), [Varon et al. 2018 transport/rate study](https://amt.copernicus.org/articles/11/5673/2018/), and [MAPL-EMIT v2](https://arxiv.org/abs/2604.10094v2). Literature synthesis and limits are in `research/literature_review.md`.
