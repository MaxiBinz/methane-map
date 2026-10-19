"""Compare a completed local replay with the preserved pre-replay measurements."""
from pathlib import Path
import json

from methane_hunter.data import sha256, utc_now, write_json

ROOT = Path(__file__).resolve().parents[1]
expected = json.loads((ROOT / "outputs/replay_expected.json").read_text())
scenes = json.loads((ROOT / "outputs/scene_metrics.json").read_text())
candidates = json.loads((ROOT / "outputs/candidates.json").read_text())
actual = [{k: c[k] for k in expected["fields"]} for c in candidates]
if scenes != expected["scene_metrics"] or actual != expected["candidates"]:
    raise AssertionError("Replayed measurement, geometry or classification values differ from the preserved run")
summary = json.loads((ROOT / "outputs/run_summary.json").read_text())
if summary["provisional"] or summary["scenes_analyzed"] != 20:
    raise AssertionError("Replay did not complete the full frozen sample")
write_json(ROOT / "outputs/reproducibility.json", {
    "verified_at": utc_now(), "status": "pass", "comparison": "exact equality",
    "scenes": len(scenes), "components": len(candidates), "candidate_fields_compared": expected["fields"],
    "scene_metric_records_compared": "all fields",
    "source_expected_sha256": sha256(ROOT / "outputs/replay_expected.json"),
    "current_manifest_sha256": sha256(ROOT / "data/nasa_input_manifest.json"),
    "command": ".venv/bin/methane-hunter analyze && PYTHONPATH=src .venv/bin/python scripts/check_replay.py",
    "non_numeric_metadata_correction": "near_region_boundary flag replaces outdated wording about missing outside-ROI catalog coverage; no numeric criterion or category changed",
    "scope_limit": "Replaying one implementation with identical inputs verifies reproducibility, not independent physical confirmation"
})
print("PASS: all 20 scene metric records and 14 component measurements/geometries/categories reproduced exactly")
