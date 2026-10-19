"""Audit the actual deliverable against the original initial-investigation scope."""
from pathlib import Path
import json
import xml.etree.ElementTree as ET

from methane_hunter.data import sha256, utc_now, write_json

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def read(path):
    return json.loads((ROOT / path).read_text())


def main():
    summary = read("outputs/run_summary.json")
    records = read("data/nasa_input_manifest.json")
    selection = read("data/metadata/nasa_selection.json")
    scenes = read("outputs/scene_metrics.json")
    candidates = read("outputs/candidates.json")
    audit = read("outputs/adversarial_audit.json")
    visual = read("outputs/visual_review.json")
    params = read("outputs/run_parameters.json")
    ids = {r["scene"]["name"] for r in records}
    require(len(records) == len(ids) == len(selection["scenes"]) == 20, "Frozen twenty-scene scope is incomplete")
    require(not summary["provisional"] and summary["scenes_analyzed"] == 20, "Only a provisional run exists")
    require({s["granule"] for s in scenes} == ids, "Metric/input scene population differs")
    checked_files = 0
    for record in records:
        for key in ["enhancement", "sensitivity", "uncertainty", "quality"]:
            entry = record["files"][key]
            require(sha256(ROOT / entry["path"]) == entry["sha256"], f"Frozen input differs: {entry['path']}")
            checked_files += 1
    for filename, digest in params["code_sha256"].items():
        require(sha256(ROOT / "src/methane_hunter" / filename) == digest, f"Analysis code changed after final run: {filename}")
    require(sha256(ROOT / "data/nasa_input_manifest.json") == params["input_manifest_sha256"], "Input manifest changed after analysis")
    require(sha256(ROOT / "data/metadata/nasa_selection.json") == params["selection_sha256"], "Scene selection changed after analysis")
    require(sha256(ROOT / "outputs/environment.json") == params["environment_sha256"], "Environment receipt changed after final run")
    for filename, digest in params["reference_catalog_sha256"].items():
        require(sha256(ROOT / "data/metadata" / filename) == digest, "Reference snapshot changed")
    require(sum(s["candidate_count"] for s in scenes) == len(candidates) == summary["screened_components"], "Component counts do not reconcile")
    require(sum(s["valid_pixels"] for s in scenes) == summary["usable_pixel_observations"], "Usable-pixel counts do not reconcile")
    cids = {c["candidate_id"] for c in candidates}
    require(len(cids) == len(candidates), "Candidate IDs are duplicated")
    for c in candidates:
        require(read("outputs/dossiers/" + c["candidate_id"] + ".json") == c, "Dossier/register mismatch")
        require(c["scene_id"] in ids, "Candidate not in the frozen sample")
        require(c["category"] in ["C", "E"], "Unverified upgraded evidence category")
        require(not c["independent_sensor_corroboration"], "Unexpected independent-sensor claim")
        require(c["emission_rate_kg_h"] is None and c["facility"] is None, "Unsupported rate/facility assertion")
    require({r["candidate_id"] for r in visual["records"]} == cids, "Visual review does not cover all candidates")
    require({r["candidate_id"] for r in audit["candidates"]} == cids,
            "Adversarial review does not cover every retained component")
    require(audit["summary"]["all_contract_checks_passed"] and not audit["summary"]["contract_errors"],
            "Adversarial component contracts did not all pass")
    require(all(r["category_after_audit"] == next(c["category"] for c in candidates if c["candidate_id"] == r["candidate_id"])
                for r in audit["candidates"]), "Audit/register category mismatch")
    require(sha256(ROOT / visual["figure"]) == visual["figure_sha256"], "Reviewed figure changed")
    validation = read("outputs/validation.json")
    require(sum(v["role"] == "positive_validation" for v in validation) == 2, "Two known-positive scenes not examined")
    require(sum(v["role"] == "control_validation" for v in validation) == 2, "Two catalog-negative controls not examined")
    require(all(v["quality_grid_check"] == "pass" and v["usable_pixels"] > 0 for v in validation), "Validation grid/quality check incomplete")
    require(summary["roles"]["search"] == 16, "Bounded search not executed")
    required = ["README.md", "research/literature_review.md", "research/research_questions.md",
                "research/methodology.md", "research/validation_protocol.md", "research/data_inventory.md",
                "reports/executive_summary.md", "reports/validation_report.md", "reports/investigative_article.md",
                "reports/component_visual_review.md", "outputs/candidates.csv", "outputs/candidates.geojson",
                "outputs/known_diagnostics.json", "outputs/adversarial_audit.json", "outputs/reproducibility.json",
                "outputs/ui_verification.json",
                "PROJECT_STATE.md", "EXPERIMENT_LOG.md", "FINDINGS.md", "OPEN_QUESTIONS.md",
                "report_app/dist/index.html"]
    require(all((ROOT / p).is_file() and (ROOT / p).stat().st_size > 0 for p in required), "Required artifact missing or empty")
    require(len(list((ROOT / "outputs/maps").glob("scene_*.png"))) == 20, "Twenty observation maps not present")
    require(read("report_app/src/data.json")["buildStatus"] == "complete", "Interactive report authoring incomplete")
    ui = read("outputs/ui_verification.json")
    require(ui["status"] == "pass" and ui["scientific_images_loaded"] == 4 and not ui["runtime_console_errors"],
            "Rendered report verification incomplete")
    require(ui["html_sha256"] == sha256(ROOT / "report_app/dist/index.html"), "Verified report build changed")
    xml = ET.parse(ROOT / "outputs/test_results.xml").getroot()
    suites = list(xml.iter("testsuite"))
    totals = {key: sum(int(s.get(key, 0)) for s in suites) for key in ["tests", "failures", "errors", "skipped"]}
    require(totals["tests"] > 0 and not totals["failures"] and not totals["errors"], "Essential test suite failed or not executed")
    transferred = 32
    for p in (ROOT / "data").glob("*download_ledger.json"):
        ledger = json.loads(p.read_text())
        transferred += sum(e["transferred_bytes"] for e in ledger) if isinstance(ledger, list) else ledger.get("total_bytes", 0)
    require(transferred < 5_000_000_000, "Download resource limit exceeded")
    result = {"checked_at": utc_now(), "status": "pass", "tests": totals, "verified_input_files": checked_files,
              "logged_scientific_data_transfer_bytes": transferred,
              "data_limit_bytes": 5_000_000_000,
              "metadata_note": "Public metadata/API response bodies are additional small transfers; logged scientific data remain far below the cap",
              "requirements": [
                  {"id": 1, "requirement": "pipeline runs on real observations", "evidence": "20 frozen full scenes; 80 hashed inputs; reconciled metric outputs", "status": "proved"},
                  {"id": 2, "requirement": "code and essential tests execute", "evidence": "JUnit test receipt and successful complete local analysis replay", "status": "proved"},
                  {"id": 3, "requirement": "known examples examined", "evidence": "2 positive scenes, 2 catalog-negative controls, detailed miss diagnostics", "status": "proved; detector sensitivity limitation documented"},
                  {"id": 4, "requirement": "at least one bounded search executed", "evidence": "16 search granules clipped to fixed ROI", "status": "proved"},
                  {"id": 5, "requirement": "all generated candidates initially assessed", "evidence": f"{len(candidates)} reconciled dossiers, adversarial records and visual-review entries", "status": "proved"},
                  {"id": 6, "requirement": "limitations documented", "evidence": "validation report, methodology, open questions, per-candidate unchecked alternatives", "status": "proved"},
                  {"id": 7, "requirement": "final package exists and is reproducible", "evidence": "Python package, lock file, frozen hashes, scripts, exports, maps and local interactive report", "status": "proved"}],
              "scientific_validation_gate": "Strong discovery claims remain closed: limited/failed conservative known-example recovery; no independently corroborated new source",
              "novel_discovery_required_for_completion": False,
              "required_artifact_hashes": {p: sha256(ROOT / p) for p in required}}
    write_json(ROOT / "outputs/completion_audit.json", result)
    print(json.dumps({k: result[k] for k in ["status", "tests", "verified_input_files", "logged_scientific_data_transfer_bytes", "scientific_validation_gate"]}, indent=2))


if __name__ == "__main__":
    main()
