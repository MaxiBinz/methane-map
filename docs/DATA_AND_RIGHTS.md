# Data, attribution, and rights

This repository combines original research code and prose, third-party report
runtime components, scientific data derivatives, and provider catalog snapshots.
Public GitHub visibility does not assign a blanket license to them.

## NASA observations

The full-scene reference inputs are NASA EMIT CH4ENH V002, CH4SENS V002,
CH4UNCERT V002, and corresponding L2A MASK V001 files. Raw files remain outside
Git. Source URLs, acquisition times, and SHA-256 hashes are retained in
[the input manifest](../data/nasa_input_manifest.json).

Credit NASA/JPL-Caltech and NASA LP DAAC. Consult the product's current usage
information and citation before reusing data:

- [EMIT methane enhancement V002](https://doi.org/10.5067/EMIT/EMITL2BCH4ENH.002)
- [EMIT methane plume complexes V002](https://doi.org/10.5067/EMIT/EMITL2BCH4PLM.002)
- [NASA Science data license information](https://science.data.nasa.gov/about/license)

## Carbon Mapper catalogs

Catalog snapshots and derived catalog associations are attributed to Carbon
Mapper. Its [terms](https://carbonmapper.org/terms), reviewed for this study with
an effective date of 13 January 2026, include attribution and noncommercial
restrictions. They are not relabeled as CC0 or unrestricted open data.
Redistribution and derived uses remain subject to the provider's terms.

Saved snapshots describe what was accessible at retrieval time. They are not a
live mirror or a guarantee of complete observational coverage.

## Code, prose, and report components

The owner has not selected a general open-source license for the original code
and prose. Copyright and applicable platform rights remain in effect. Existing
third-party notices in the report runtime remain applicable to those components;
this repository does not claim ownership of their implementation.

The project was developed with AI assistance. Scientific claims refer to saved
observations, deterministic calculations, and documented checks. AI-generated
interpretation is not an independent sensor, a field observation, or a substitute
for scientific validation.

## Coordinates and interpretation

Candidate geometries describe enhancement support. They do not establish a
facility's responsibility or an emission source's identity. Category E means an
association with a published observation neighborhood; Category C means ambiguous
evidence. Novelty is assessed separately and was not established in this study.
