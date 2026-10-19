# Research questions and claim boundaries

Written 2026-10-18. These are proposed questions and decision rules, not findings. Execution status is recorded in `PROJECT_STATE.md` and `EXPERIMENT_LOG.md`.

## Primary question

Within one fixed geographic region and approximately 20 eligible EMIT observations, can a reproducible CPU pipeline identify methane-like enhancement components that are absent from a dated NASA plume-catalog snapshot and survive initial adversarial review?

An unmatched component is an **uncataloged enhancement candidate**. It is not automatically a plume, a geographic source, a facility, an emission rate or a new discovery. An inaccessible catalog produces **match unknown**, never **unmatched**.

## Questions in priority order

1. **Access and measurement integrity.** Can numeric V002 enhancement, uncertainty, sensitivity, georeferencing and enough quality context be obtained within 5 GB? Are their units and missing-data conventions understood? Failure here limits the product to infrastructure/access findings and any explicitly narrower real-data experiment.
2. **Known positives.** Does fixed screening recover at least two documented complexes in different scenes, with sensible spatial association and separated local background? Record misses. This is a small positive-control check, not a global sensitivity estimate.
3. **Catalog-negative controls.** Can at least two full scenes without catalog matches be examined with observational quality assessed? A different image date or neighboring crop inside a known-plume product is not automatically a full-scene negative control. Controls may contain real uncataloged gas; report component counts rather than calling every component a false positive.
4. **Bounded search.** Among eligible region observations, which connected enhancement components lie outside same-acquisition catalog outlines after a documented spatial tolerance? Retain catalog revision, date matching, scene relationships and coverage limitations.
5. **Falsification.** Which candidates disappear when screening choices change, align with stripes, occur near invalid/cloud boundaries, track surface patterns, fail spatial alignment or have corroborating prior documentation? Does any independent sensor or radiance-based check support a surviving candidate?

## Competing hypotheses

- H1: A component reflects atmospheric methane above its local background.
- H2: It reflects surface spectral contrast or illumination effects.
- H3: It reflects cloud/shadow, water, hot pixels, low sensitivity or retrieval noise.
- H4: It reflects detector geometry, resampling or geolocation errors.
- H5: It is real methane already documented under a different complex, scene, time or catalog.

Each candidate dossier must retain evidence for and against these alternatives. Missing corroboration is recorded as missing evidence, not evidence for H2 or H3.

## Valid outcomes

A working pipeline with recovered known examples; a failed detector; an ambiguous uncataloged candidate; no unmatched components within the tested population; or an honest access/quality blocker are all acceptable. A zero candidate count establishes no more than the result for the measured sample and specified detector.

## Evidence and novelty are separate fields

Use the user's categories: A independently corroborated observation; B credible but uncorroborated; C weak/ambiguous; D rejected/explained; E previously documented. Also record novelty independently as `previously_documented`, `not_established`, or `supported_by_specific_search` with exact search scope and date. Category A does not establish novelty. A repeated retrieval of the same photons is algorithmic agreement, not independent atmospheric corroboration.
