# A real methane search ran; its detector still misses known observations

Methane Hunter analyzed twenty NASA EMIT V002 enhancement granules over the northern Delaware Basin, using observations from 24 December 2023 to 22 September 2025. The CPU pipeline processed 15.9 million usable pixel-observations across sixteen dates, applied official quality flags and compared screening components with a saved Carbon Mapper methane catalog.

**The first investigation does not establish a new methane source. Its most useful result is a demonstrated sensitivity limitation.** The frozen baseline associated a retained component with a known observation in only one of its two positive-validation scenes. It therefore did not pass the planned two-scene positive-recovery gate.

- **Bounded search:** sixteen search granules produced four baseline components. All four were associated with published same-acquisition catalog neighborhoods; none was an independently corroborated new observation.
- **All analyzed roles:** fourteen components were retained. Six were category E (documented-observation neighborhood associations), and eight remained category C (ambiguous). All eight C components came from the 23 March 2025 positive-validation scene. Components are not unique physical plumes or sources.
- **Controls:** two catalog-negative scenes retained zero baseline components over 572,084 usable pixel-observations. Their absence of cataloged plumes does not establish methane-free truth or a calibrated false-positive rate.
- **Why the detector missed known examples:** the unchanged baseline used a 500 ppm m floor and five times both local robust scatter and sensor uncertainty, with at least four connected pixels. A prespecified three-times diagnostic recovered associations in both positive scenes; seven-times recovered none. Quality exclusion and the minimum support also affected known examples. This was a sensitivity experiment, not a replacement baseline or independent validation.

A separate audit and visual review covered all fourteen components. It flagged two possible fragment pairs, two ambiguous components within 1 km of a same-acquisition catalog source, and six components near quality-excluded context; none was upgraded, rejected or proven contaminated.

The research package contains source hashes, input and processing manifests, per-scene maps and metrics, the candidate register and an initial dossier for every component. Reported coordinates describe enhancement geometry. No facility responsibility, emission rate or annual emissions were inferred.

A complete local replay reproduced all twenty scene-metric records and the fourteen components’ compared numeric, geometric and category fields exactly. The essential test suite passed **56 tests, with no failures, errors or skips**. Reproducibility is a software result, not independent atmospheric confirmation.

The next useful experiment is an independent spectral/context review of the eight ambiguous components, coupled with a scientifically justified detector validation on a larger held-out set. Lowering a threshold merely to recover attractive features would not solve the physical-validation problem. Regional catalog completeness cannot be inferred from this small, provider-influenced sample or this detector's non-detections.

Evidence: [final run summary](../outputs/run_summary.json), [validation rows](../outputs/validation.csv), [known-example diagnostics](../outputs/known_diagnostics.json), [candidate register](../outputs/candidates.csv), [frozen protocol](../research/validation_protocol.md). The numeric summary describes this execution; current provider archives may differ from the retained snapshots.
