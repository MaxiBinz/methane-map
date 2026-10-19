# We searched public satellite methane data. The first finding was a detector that misses known plumes.

A bright patch in a satellite methane image can look persuasive. Whether it marks gas, a problematic surface, cloud contamination or a processing artifact is a harder question. Methane Hunter's first investigation set out to test that distinction with real observations before claiming a discovery.

The result is a working, reproducible pipeline and a failed sensitivity gate. Twenty NASA EMIT granules over the northern Delaware Basin were processed with their uncertainty, sensitivity and official quality data. The predefined detector recovered a known-observation association in one of two positive-validation scenes. Its bounded search found four screening components, each associated with a published observation neighborhood. No independently corroborated new methane source emerged.

## Why look beyond a plume catalog?

EMIT was built to study Earth's surface mineralogy. Scientists demonstrated that its imaging spectra also reveal strong methane point-source enhancements. NASA's V002 enhancement product makes scene-wide retrievals available, including scenes without an identified plume complex. That creates a testable opportunity: compare numerical observations with conservative, incomplete catalogs and investigate unexplained responses.

It does not make discovery automatic. Hyperspectral measurements contain surface and atmospheric confounders. A conservative human-reviewed catalog can miss real weak enhancements, while an automated detector can produce false features. The established scientific literature, including the 2026 MAPL-EMIT preprint, already addresses automated detection and spectral vetting. This project did not train a new model or reproduce MAPL's benchmark performance; it tested a transparent CPU baseline on a manageable real sample. [NASA V002](https://doi.org/10.5067/EMIT/EMITL2BCH4ENH.002), [Thorpe et al. 2023](https://authors.library.caltech.edu/records/50nm7-ayj24), [MAPL-EMIT](https://arxiv.org/abs/2604.10094v2).

## An access problem came before an atmospheric one

Public metadata was easy to retrieve. The scientific raster files initially required authentication. The investigation first checked public numeric plume exports, then verified that these products mask their output to selected plume support. Using that already selected support as neutral background would make a detector test circular. Those exports were therefore kept separate from full-scene controls.

User-authorized Earthdata access enabled the main investigation: twenty frozen enhancement scenes, paired sensitivity and sensor-noise uncertainty rasters, and matching quality masks. Credentials were kept out of the source and research outputs. The fixed geographic box covers longitude 104.5–102.5°W and latitude 31–33°N; observation dates run from 24 December 2023 to 22 September 2025.

The sample contains two documented-positive scenes, two scenes without published plumes in the saved provider metadata and sixteen search scenes. It was chosen using available provider coverage and scene metadata, so it is a convenience sample rather than a regional census. Several granules share an overpass, and the resulting 15.9 million usable pixel-observations should not be read as 15.9 million independent measurements or unique land pixels.

## A strict screen did not reproduce both known examples

The detector corrected NASA enhancement for sensitivity, retained official quality-approved pixels, and estimated local background with robust statistics. A candidate needed at least four connected pixels above 500 ppm m and five times both robust background scatter and supplied sensor uncertainty. The latter describes instrument noise; it does not account for every surface artifact. These are exploratory screening criteria, not a validated physical plume classifier.

On 23 August 2024 the baseline produced no components despite four published Carbon Mapper source heads in the region. On 23 March 2025 it produced ten components, but only one of ten source heads was associated at the primary 300 m rule. Two components lay near that same head, illustrating why component count cannot be equated with source count.

The negative-control scenes produced no retained components. That sounds reassuring until the reference standard is examined: having no cataloged plume does not guarantee clean air. A detector that rarely fires can also have poor sensitivity. Zero controls and a missed known scene cannot establish a calibrated false-positive rate or a successful methane detector.

A fixed diagnostic helped explain the misses. At a three-times criterion, retained components associated with two of four heads in the first positive scene and seven of ten in the second. At seven-times, neither scene retained such an association. In the first scene, the three-times components intersected two of three NASA plume outlines. Cloud-buffer exclusions removed some reference neighborhoods, and other weak features failed noise or minimum-support requirements. The baseline was left unchanged; the diagnostic was evidence about its limitations, not an excuse to select a more exciting answer.

NASA's exact-start-time plume query returned no outlines for the second scene, while Carbon Mapper listed documented observations. That discrepancy must stay unresolved at the correct level: catalog definitions, scene-spanning timestamps and retrieval versions can differ. An empty exact-time response is not evidence that a provider's gas observation was false.

## Four search components were already documented; eight other responses stayed ambiguous

Across all twenty granules, the baseline generated fourteen screening components. Six received category E because they lay in a published same-acquisition source neighborhood. Eight received category C because the evidence was ambiguous. All eight C components came from the 23 March 2025 positive-validation scene, and none received an upgrade to a credible or independently corroborated methane finding.

In the sixteen search granules, there were four baseline components, all category E. That is a narrow result about this sample and method. It does not show that the catalogs are comprehensive: the positive checks already demonstrate that the detector misses documented features.

Each component has a structured dossier containing its scene and timestamp, enhancement statistics, geometry, uncertainty, quality checks, catalog associations and alternative explanations. Coordinates label enhancement centroids, not inferred emitters. Same-acquisition catalog agreement is documentation from the same observation, not an independent sensor measurement. No facility was assigned responsibility, and no emission rate or annual emissions were calculated.

## A skeptical review kept the alternatives open

A separate reproducible audit checked every component's timing, geometry, source metadata, catalog neighborhood, quality support and local background context. All fourteen passed those structural checks. The actual numeric-data panels were also visually inspected. Neither exercise independently confirmed methane, and neither changed a category.

The review found two pairs that could be threshold fragments of one visible feature. Two ambiguous components were 650–920 m from a documented same-acquisition source, leaving plume extensions as an alternative to separate emissions. Six components were within 1.5 km of a quality-excluded pixel center, but no retained component contained excluded-quality pixels. Such proximity warrants scrutiny; it is not proof of cloud contamination.

Some responses were compact bright clusters without a distinctive extension. Other responses formed parts of larger elongated features. Without spectra, surface context or independent winds, morphology cannot decide which interpretation is right. The audit therefore preserved all eight ambiguous components as category C and all six documented-neighborhood associations as category E. A failed attempt to reject a feature is not itself confirmation of methane or novelty.


## What the evidence supports next

The initial pipeline can discover and download observations, map quality flags, process actual methane retrievals, draw maps and produce a traceable candidate register. It has also exposed a scientifically material limitation: successful software execution did not yield adequate known-example recovery for strong discovery claims.

The eight ambiguous responses are appropriate targets for an independent spectral and surface-context check. A convincing next test would examine radiance absorption, nearby surface spectra and high-resolution context, then seek another instrument or near-coincident observation where feasible. Observation-time winds could support transport interpretation, but morphology alone cannot supply that evidence. Improving the detector requires a held-out validation design, including real positives and carefully characterized controls, rather than optimizing thresholds on these twenty scenes.

A complete local replay then reproduced every scene-metric record and the compared numerical, geometric and category fields for all fourteen components. The essential software suite passed 56 tests without a failure, error or skip. That repeatability makes the investigation inspectable; it does not transform an ambiguous retrieval into independently confirmed gas.

The honest finding is therefore methodological: this first autonomous investigation ran on real data, documented its own failure to reproduce enough known observations, and left unsupported discovery claims out of the report.

Evidence package: [final summary](../outputs/run_summary.json), [per-scene measurements](../outputs/scene_metrics.csv), [known-example diagnostics](../outputs/known_diagnostics.json), [candidate register](../outputs/candidates.csv), [validation report](validation_report.md), [methodology](../research/methodology.md) and [literature review](../research/literature_review.md). NASA data are attributed to NASA/LP DAAC; Carbon Mapper catalog data are attributed to Carbon Mapper and remain subject to its [terms](https://carbonmapper.org/terms).
