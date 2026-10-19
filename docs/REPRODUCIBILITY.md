# Reproduce the investigation

The reference investigation completed on 19 October 2026. It used Python 3.12.14
on macOS ARM and retained 20 full NASA scenes, 80 input files, their hashes, the
baseline parameters, and source catalog snapshots. No independently corroborated
new methane source was established.

## Install

From a clone of this repository:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pytest -q
```

`requirements.lock.txt` records the project's scientific dependency closure from
the reference environment. It contains no editable local paths or unrelated
document-generation packages. Platform-specific wheels can differ; identical
binary-level results on a different operating system are not assumed.

## Preserve the reference evidence

Checked-in outputs and manifests describe the original run. Acquisition,
analysis, diagnostics, and audit commands write new receipts to these paths.
Use a separate clone or copy for a replay, keeping the published Git commit
available for comparison.

- [Frozen selection](../data/metadata/nasa_selection.json)
- [Input hashes and source context](../data/nasa_input_manifest.json)
- [Baseline and code hashes](../outputs/run_parameters.json)
- [Reference environment](../outputs/environment.json)
- [Original exact replay receipt](../outputs/reproducibility.json)
- [Completion audit](../outputs/completion_audit.json)

## Reacquire the raw inputs

Use a NASA Earthdata account with access to the listed products:

```sh
.venv/bin/methane-hunter fetch-nasa
```

The hidden prompt accepts an Earthdata bearer token without terminal echo. A
securely configured `EARTHDATA_TOKEN` environment variable is also supported.
Never put credentials in source, issues, notebooks, shell arguments, or Git.
If a credential has been shared in chat or elsewhere, revoke it at the provider
and use a replacement.

The code restricts authenticated requests to the verified NASA data host, keeps
hashes and transfer receipts, and enforces the 5 GB data budget. Original logged
scientific transfers totaled **1,772,660,316 bytes**, including access checks and
supplementary exports; metadata traffic is additional and small. The main 80
NASA files account for **1,771,331,470 bytes**.

Do not erase byte ledgers to defeat the limit. Stop if a transfer would exceed
the remaining allowance. A changed upstream hash defines a new product version;
it cannot be described as the identical original input. Raw data remain outside Git.

## Run the analysis and diagnostics

```sh
.venv/bin/methane-hunter analyze
PYTHONPATH=src .venv/bin/python scripts/diagnose_known.py
PYTHONPATH=src .venv/bin/python scripts/audit_candidates.py
PYTHONPATH=src .venv/bin/python scripts/make_figures.py
PYTHONPATH=src .venv/bin/python scripts/check_replay.py
```

The analysis verifies frozen hashes before processing. The replay comparator
uses the preserved expected values; it compares measured and geometric fields,
not newly generated timestamps. The original E05 replay reproduced all 20 scene
records and the compared fields for 14 components exactly. Repeating the same
implementation on the same inputs checks computation, not independent gas truth.

## Open the saved interactive report

```sh
python3 -m http.server 4173 --bind 127.0.0.1 --directory report_app/dist
```

Open `http://127.0.0.1:4173/?view=1`. Serve the whole directory: the HTML and its
content-addressed JSON sidecar form one verified build. The map, component
selector, figures, and source inspector describe the reference run, not a live
NASA service.

The report's supported authoring workflow is in `report_app/AGENTS.md` and
requires its installed Data authoring tools. Opening the checked-in build only
requires a local HTTP server. Python output changes do not rebuild the report.

## Understand the validation boundary

The convenience sample contains 2 positive scenes, 2 catalog-negative controls,
and 16 search granules across 16 dates. The positive gate failed: 0 of 4 reference
heads were associated in the first positive scene and 1 of 10 in the second at
the primary tolerance. Zero components in controls does not establish a calibrated
false-positive rate. Independent spectral, surface, wind, and sensor checks
remain outstanding. See [the validation report](../reports/validation_report.md).
