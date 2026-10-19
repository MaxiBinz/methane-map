# Methane Hunter research state

Status: initial investigation completed, including its documented unsuccessful
conservative detection-validation gate. All five iterations, numerical replay,
essential tests, complete component assessments and interactive-report checks
are finished. Started 2026-10-18 (Europe/Vienna), completed 2026-10-19.

## Authorized scope

One bounded region: northern Delaware Basin / Permian Basin, WGS84
[-104.5, 31.0, -102.5, 33.0]. Approximately 20 useful scenes, at most
5,000,000,000 downloaded data bytes, at most five substantive analysis iterations.
CPU only; free public services; the original study stayed local. No discovery is required.

## GitHub publication

On 19 October 2026 the owner authorized publication of the code and findings to
the public repository `MaxiBinz/methane-map`. The GitHub package includes the
research narrative, source, retained evidence, figures, and saved interactive
report. Raw satellite inputs and credentials remain excluded. The repository
does not deploy a public website. Publication cleanup preserves the frozen
numerical outputs and classifications.

## Current evidence

- Empty project inspected; roughly 758 GB disk available at initialization.
- System Python lacks scientific packages. Project `.venv` uses Python 3.12.14
  and scientific dependencies; installation succeeded.
- Sandboxed shell DNS unavailable; approved public read-only network works.
- NASA CMR CH4ENH V002 collection and 20 regional granule metadata records saved.
- Earthdata bearer access was verified with HTTP 206 and TIFF magic bytes.
  Credentials were entered through hidden terminal input and kept in memory.
- All 20 frozen full scenes downloaded: enhancement, sensitivity, sensor
  uncertainty and L2A MASK. NASA data transfer ledger: 1,771,331,470 bytes.
- Two supplementary public plume exports total 1,328,814 bytes. One has no
  valid pixels inside the ROI and is excluded from regional results.
- Real quality-mask GLT mapping passed on the downloaded scenes checked so far.
- Fifty-six software tests pass. These fixtures do not establish real sensitivity.
- E01: two known-positive and two catalog-negative scenes analyzed. Baseline
  returns 0 and 10 components in positives, 0 in each control; one positive
  scene has a same-acquisition catalog-neighborhood association. The baseline
  missed the other positive scene. Strong discovery validation is not passed.
- E02 completed: quality buffering, thresholds and small disconnected supports
  explain conservative reference misses. Baseline parameters stayed unchanged.
- E03 completed: all twenty granules analyzed. Four components in sixteen search
  granules are all catalog associated. Whole sample: six E and eight C components;
  all C components occur in the second positive-validation scene.
- E04 completed: all fourteen components audited and visually reviewed; categories
  unchanged. No independent novel-source corroboration.
- E05 completed numerical replay: all twenty scene records and fourteen component
  measurements/geometries/categories agree exactly with the preserved run.

## Validation gate

Require two documented positive scenes and two independently selected scenes
without cataloged plumes, with quality assessment, before strong search claims.
If full-scene data or controls remain inaccessible, report an incomplete gate.

## Next action

The requirement audit is `outputs/completion_audit.json`; UI evidence is
`outputs/ui_verification.json`. Strong discovery claims remain gated by the
incomplete detection-sensitivity and independent physical evidence. No further
substantive experiment is authorized inside this initial five-iteration loop.
The next scientific step is independent spectral/surface/wind corroboration and
separate calibration/holdout validation, as described in `OPEN_QUESTIONS.md`.

