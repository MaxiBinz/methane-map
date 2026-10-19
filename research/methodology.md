# Initial investigation methodology

Design recorded 2026-10-18. This document defines the scientific contract. Exact executed parameters, input hashes, sample and outcomes must be read from the run manifest and reports; proposed steps below are not evidence that they ran.

## Scope, data hierarchy and stop conditions

Use one bounded region, roughly 20 useful observations, no paid services, local CPU processing and at most five substantive experiments. Count failed scientific experiments in the log, while distinguishing routine implementation repairs. Enforce the 5 GB cap on actual downloaded bytes, including partial/failed payloads where measurable. Cache numeric observations so reruns need not download them again. Do not publish externally.

Prefer full-scene EMITL2BCH4ENH V002 with matching CH4UNCERT and CH4SENS, plus same-scene quality masks/RGB context and CH4PLM V002 catalog outlines. Product identifiers and units are documented in the [NASA product](https://doi.org/10.5067/EMIT/EMITL2BCH4ENH.002) and [SDS user guide](https://github.com/emit-sds/emit-sds-tgp/blob/develop/docs/EMIT_L2B_TRACE_GAS_User_Guide.md).

If only a known-plume crop can be obtained, run numeric reader/geolocation/positive-recovery checks and label them as such. Crops cannot support scene-wide specificity, full-region completeness, unbiased novelty search or replacement of the required two catalog-negative scenes. A colorized browse image is qualitative context and must never be inverted to manufacture ppm m measurements.

## Sampling and provenance

1. Query NASA CMR for the exact V002 collections and region/time interval. Save raw responses, pagination, query parameters and UTC retrieval times. Query the full relevant catalog window before selecting negatives. Explicitly test spatial footprint overlap; bounding-box overlap alone can include unobserved area.
2. Select positives using catalog evidence before looking at enhancement strength. Select catalog-negative scenes separately; predefine chronology/quality ranking and explain any exclusion. Freeze scene IDs to prevent selecting only attractive results. Keep analysis coordinates inside the stated region.
3. Record provider, instrument, observation time, source granule, acquisition/scene relationships, download URL, DOI/version, local path, content hash, bytes, retrieval timestamp and transformations. Retain source licensing. Keep secrets outside files and avoid storing temporary signed credentials in the manifest.
4. Preserve archive originals. If a service returns subsets or resampled arrays, record output shape, CRS, transform, scale/offset, nodata, resampling and pixel spacing. Distinguish observation date from publication/access date. A catalog snapshot can lag the acquisition.

## Numeric and geospatial integrity checks

Use the raster metadata and valid-data mask rather than equating zero or negative enhancement with missing data. Check CRS, transform, raster dimensions, bounds, dtype and nodata. Derive pixel-center coordinates using the affine transform. Test alignment of the three layers before combining them; resample only with an explicit reason and preserve a record. Do not treat nominal 60 m as a fixed pixel width everywhere in EPSG:4326; compute areas/distances geodesically or in an appropriate local metric CRS.

Read sensitivity as a unitless retrieval quantity rather than a cloud flag. Preserve both original and corrected enhancement when correction is performed. The [NASA ATBD](https://github.com/emit-sds/emit-sds-tgp/blob/develop/docs/EMIT_L2B_TRACE_GAS_ATBD.md), sections 4.2.2 and 6.2, is the controlling convention: check whether per-pixel uncertainty already incorporates sensitivity before applying transformations. Use scene/background scatter alongside instrument-noise uncertainty. Missing uncertainty means unavailable, not zero. A signal/noise ratio is a screening statistic rather than a calibrated discovery probability.

## Transparent baseline candidate generation

The proposed baseline screens an existing spectroscopic methane retrieval; it does not create a new physical retrieval. Estimate a robust background center and scale from valid neighboring/scene pixels with an explicitly specified method. If MAD is used, report `1.4826 * median(abs(x - median(x)))`, support size and the treatment of spatial variation. Avoid estimating background solely inside a catalog plume crop.

Apply a documented enhancement threshold together with a background-relative threshold and, where scientifically interpretable, an instrument-noise gate. Label connected components and require a predefined minimum support. Store the exact thresholds, connectivity and smoothing in the run parameters. Calculate pixel count, enhancement distribution, geometry and background contrast. Retain negative values during background estimation. Never translate a connected-component score into an emission rate.

Freeze the baseline before evaluating search scenes. Evaluate a small preregistered parameter neighborhood to expose fragility; do not select the setting that produces the most novel-looking components. Connected-component morphology and robustness are suggested screening choices of this project, not a validated NASA or MAPL plume classifier.

## Positive and control validation

Examine at least two documented plumes from different scenes and at least two suitable catalog-negative full scenes. Associate by actual outline and acquisition/scene mapping, with a pixel-scale/geolocation tolerance stated in meters. Record intersection, distance and missed positives, rather than counting a nearby but distinct component as recovery. Avoid calling the catalog coordinate of maximum enhancement a physical source.

Report small-sample recovery as counts with the denominator. Report control component burden per valid area and quality stratum, without assuming every control component is false. Document cloud/water/invalid fractions, sensitivity and noise distributions, boundary proximity and striping where data permit. If quality cannot be assessed, record the validation gate as incomplete. A successful code test does not establish scientific sensitivity or specificity.

## Catalog matching and bounded search

Search only after the positive/control gate is assessed. Report exploratory output even when validation fails, with a clear prohibition on strong plume or novelty claims. Query NASA and, if permitted/accessible, Carbon Mapper separately. Match same-observation complexes first; search prior/repeat observations separately. Use buffered outlines and timestamps/granule relationships, not a broad spatial-only nearest neighbor. Mark incomplete pagination, inaccessible providers or unresolved duplicate IDs explicitly.

A catalog match can justify E (documented) for the observed feature but does not provide independent corroboration if both products derive from the same acquisition. A missing match means no match within the queried snapshots and rules. It does not prove prior scientific ignorance, catalog incompleteness at all thresholds or facility culpability.

## Adversarial review and independent checks

For every component, retain a dossier addressing cloud/shadow boundaries, surface/RGB correlation, low sensitivity, hot pixels, striping, geolocation, nodata leakage, duplication and existing literature/catalog matches. Compare available repeated observations at the same ground location to distinguish fixed surface structure from changing atmospheric morphology. A repeated feature alone can reflect either persistent gas or persistent surface bias.

Use a different verification method where feasible: inspect radiance gas absorption relative to nearby background; run vetted MAPL/radiance inference if prerequisites fit the budget; or compare a near-coincident independent sensor/airborne observation. Re-thresholding the same enhancement array is only a robustness check. Wind-direction agreement requires measured/modelled observation-time winds and uncertainty. Morphological consistency alone is not wind validation. The [MAPL repository](https://github.com/google-research/mapl) was reviewed as an existing detector; its inference is not claimed unless run inputs and outputs are present.

Assign A–E evidence categories conservatively and keep novelty separate. Missing RGB, raw spectra, masks, wind or independent observations must remain explicit. Category B requires affirmative artifact challenges; C is appropriate when strong retrieval values remain poorly verified. Do not use absence of corroboration as a rejection by itself.

## Source attribution and emission rates

Report a geometric centroid or enhancement maximum with that label. Assign a probable source only with transport and high-resolution context. Name a facility only when the evidence supports its location and connection to the observed gas. Leave source/facility fields null when unknown.

The [Varon et al. 2018 transport study](https://amt.copernicus.org/articles/11/5673/2018/) and [Cusworth et al. 2019 retrieval study](https://amt.copernicus.org/articles/12/5655/2019/) justify a strict rate gate: suitable plume segmentation, observation-time wind, unit/pressure/temperature conversions and method calibration with uncertainty must all be available. This initial baseline need not estimate rates. Provider-published rates, if quoted, remain attributed provider estimates. Do not infer annual emissions or source persistence from a single pass.

## Deliverables and reproducibility

Export the selected-scene table, candidate CSV/GeoJSON, source manifest, numeric metrics, maps, validation report and a dossier for every generated candidate. Distinguish observations, ambiguous screening components and known documentation visually. Plot legends must state ppm m and whether values are corrected/resampled. A local map may show observed footprints and candidate geometries but must not imply unsampled areas are methane-free.

Tests should check mask/nodata treatment, raster alignment, coordinate transforms, connected-component behavior, catalog association and resource caps. Synthetic fixtures are legitimate software tests and must be labelled synthetic; only real satellite arrays enter scientific findings. Record software versions and commands. Maintain project state, findings, questions and the five-iteration experiment log. Explicitly state which definition-of-done criteria remain unmet if access or scientific validation prevents completion.
