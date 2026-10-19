# Experiment log

Access checks and software setup are preparatory work, not evidence of methane.

Preparatory record, 2026-10-18: NASA CMR returned CH4ENH V002 collection
C3242680113-LPCLOUD and 20 recent metadata records overlapping the fixed region.
Commands and exact parameters will be retained in the source manifest. Package
installation and metadata discovery do not establish retrieval accuracy.

## E01 — Known-example and catalog-negative validation (2026-10-19)

- Hypothesis: the frozen conservative screen will retain enhancements near
  known positive references while producing a bounded output in controls.
- Inputs: first four records in `data/nasa_input_manifest.json`, representing
  two known-positive scenes and two Carbon Mapper catalog-negative scenes;
  ENH/SENS/UNCERT V002 and L2A MASK V001. Selection and exact hashes are recorded
  in `outputs/run_parameters.json` and the input manifest.
- Method: enhancement/SENS; supplied UNCERT unchanged; exact L2A GLT mask;
  fixed geographic clipping; floor 500 ppm m, five times local robust scale and
  sensor uncertainty, four connected pixels minimum. Three/seven multipliers
  are a prespecified sensitivity diagnostic, not retuned final thresholds.
- Command: `PYTHONPATH=src .venv/bin/python -m methane_hunter.cli analyze --limit 4`.
- Results: positives returned 0 and 10 baseline components, with 0/4 and 1/10
  CM reference heads associated within 300 m of component support and 120 s.
  Controls returned zero components; usable pixel counts were 559,665 and
  12,419, so control exposure is strongly unequal. At multiplier three,
  positives returned 5/113 components and controls 7/0; at seven, 0/1 and 0/0.
- Validation outcome: numeric reads, ancillary alignment and masking execute;
  the conservative detection-sensitivity gate is incomplete. No specificity,
  false-positive probability or discovery claim follows from these controls.
- Limitations: references share the EMIT instrument, source heads differ from
  enhancement support, some heads may be quality excluded, and catalog-negative
  scenes can contain methane. Current reference comparison uses CM; exact
  NASA outlines are being added to avoid calling a known plume unmatched.
- Next action: E02, diagnose misses without changing baseline thresholds.

An initial implementation run stopped on a catalog-ID string parsing error
before producing a valid scene result. The bug was corrected and the command
above completed. This is a software failure, not a separate scientific result.

## E02 — Diagnose known-example misses without retuning (2026-10-19)

- Hypothesis: failed reference recovery can be explained by explicit quality,
  sensor-noise, background or connectivity criteria rather than a broken reader.
- Inputs: the same two positive scenes, 14 scene-scoped CM source heads and
  three exact NASA CMR plume outlines at the first positive timestamp. The full
  sample has 13 NASA outlines across seven timestamps; those are not all positive
  validation references. Hashes are in `outputs/known_diagnostics.json`.
- Method: inspect 300 m and 1 km source-head neighborhoods, exact NASA polygon
  overlap, flag values, raw/corrected enhancement, sensor/background contrasts,
  pre-filter cluster sizes and the prespecified 3/5/7 multipliers.
- Command: `PYTHONPATH=src .venv/bin/python scripts/diagnose_known.py`.
- Results: two first-scene head neighborhoods have zero usable pixels within
  300 m specifically because of the dilated-cloud flag. Other first-scene known
  features produce only one-/two-pixel baseline clusters. At multiplier three,
  two of four CM head neighborhoods and two of three NASA outlines associate;
  the second scene associates seven of ten CM heads within 300 m (eight within
  1 km). At baseline five the second scene associates one within 300 m and three
  within 1 km. Remaining misses include below-threshold sensor signals and
  fragmented one-/two-pixel supports.
- Validation outcome: the reasons for conservative misses are reproducible.
  Relaxing thresholds substantially increases components, including seven in
  one catalog-negative control. Baseline parameters remain unchanged.
- Limitations: same-EMIT catalog agreement and same-retrieval local-background
  checks are not independent atmospheric confirmation. Neither these counts nor
  reference masks estimate population sensitivity/specificity.
- Next action: E03, run the bounded frozen sample while retaining a closed gate
  for strong discovery claims.

## E03 — Bounded exploratory screen (2026-10-19)

- Hypothesis: the frozen region/sample may contain robust connected enhancements
  not associated with the finite existing catalog snapshots.
- Inputs: 20 full ENH/SENS/UNCERT/MASK granules; two positives, two controls and
  sixteen search granules; 16 dates from 2023-12-24 to 2025-09-22. Exact hashes,
  requests and versions are saved. No additional geographic region was added.
- Method: unchanged baseline; exact quality masks and region clipping; CM
  source-to-support distance <=300 m and time <=120 s; positive-area intersection
  with exact NASA published outline vertices. Source-head context outside the
  ROI is included through per-scene catalog queries.
- Command: `.venv/bin/methane-hunter analyze`.
- Results: 15,917,415 usable pixel-observations, 14 retained components: six
  Category E catalog associations and eight Category C ambiguous components.
  The sixteen search granules return four components, all Category E. All eight
  unmatched components occur in the second positive-validation scene.
- Validation outcome: real numerical/geospatial pipeline executes across the
  complete sample. No independently corroborated new methane source, facility
  attribution or emission rate is established. The conservative sensitivity
  failure prevents completeness or strong discovery claims.
- Limitations: selected sample, unequal usable coverage, 16 dates rather than
  20 independent revisits, retrieval differences, finite catalogs and empirical
  thresholds. Counts are components, not unique plumes or emissions events.
- Next action: E04, attempt to explain every retained component.

## E04 — Adversarial component and visual review (2026-10-19)

- Hypothesis: duplicates, wider known-source context, weak local contrast,
  quality proximity or invalid provenance may explain apparent unmatched output.
- Inputs: all 14 component dossiers, raw quality masks, frozen catalogs and
  actual enhancement maps. No further satellite downloads.
- Methods/commands: `PYTHONPATH=src .venv/bin/python scripts/audit_candidates.py`;
  `PYTHONPATH=src .venv/bin/python scripts/make_figures.py`; visual inspection of
  all 14 panels in `outputs/maps/component_review.png`.
- Results: all 14 provenance/geometry/catalog contracts pass; no component
  contains a selected excluded-quality pixel. Two neighboring component pairs
  may be fragmented features. Two C components have same-acquisition known
  source heads 300 m–1 km away. One C component has weak annular contrast (2.82).
  Six components lie within 1.5 km of excluded quality pixels; proximity alone
  does not establish contamination. No cross-date retained-component recurrence
  was found using the specified 1 km neighborhood rule.
- Validation outcome: every component has an initial adversarial assessment and
  a visual-review entry. Categories remain E=6/C=8; no heuristic alone justifies
  rejection or an upgrade to independent corroboration.
- Limitations: radiance spectral fitting, surface reflectance comparison,
  independent wind fields and another sensor remain unchecked. The eight C
  components cannot be called novel emissions. Review notes are in
  `outputs/adversarial_audit.json` and `outputs/visual_review.json`.
- Next action: E05, verify exact reproducibility and complete the report package.

## E05 — Local reproducibility and final package verification (2026-10-19)

- Hypothesis: the saved input files and code reproduce the numerical, geometric
  and evidence-category results exactly without additional downloads.
- Inputs: the same 80 hashed NASA files and fixed catalogs. Pre-replay results
  are preserved in `outputs/runs/E03/` and `outputs/replay_expected.json`.
- Commands: `.venv/bin/methane-hunter analyze`;
  `PYTHONPATH=src .venv/bin/python scripts/check_replay.py`;
  `.venv/bin/python -m pytest -q --junitxml=outputs/test_results.xml`;
  `PYTHONPATH=src .venv/bin/python scripts/verify_package.py`.
- Results: all 20 scene metric records and all 14 component measurement,
  geometry and category records reproduce exactly. The essential suite has
  56 passing tests, zero failures/errors/skips. The final package audit is saved
  in `outputs/completion_audit.json` after report verification.
- Metadata correction: one boundary flag was renamed `near_region_boundary`
  because per-scene catalog context now includes source heads outside the ROI;
  no numeric criterion, geometry or category changed.
- Limitations: identical-code replay and passing tests establish software
  reproducibility, not independent scientific confirmation.
- Next action: stop the initial five-iteration loop. Any subsequent scientific
  work should target independent spectra/surface/wind evidence and a separate
  calibration/holdout design, not lower thresholds until a discovery appears.

