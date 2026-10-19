"""Create a portable local research bundle, excluding raw data and credentials."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
destination = ROOT / "methane_hunter_research.zip"
files = set()
for directory in ["src", "scripts", "tests", "research", "reports", "outputs", "data/metadata", "report_app", "docs", ".github"]:
    for path in (ROOT / directory).rglob("*"):
        if (path.is_file() and not any(part in {"__pycache__", "node_modules", ".data-app", ".data-app-offline", ".openai"} for part in path.parts)
                and path.suffix != ".pyc" and path.name not in {".DS_Store", "UPDATE_CONTRACT.md"}):
            files.add(path)
for name in ["README.md", "pyproject.toml", "requirements.lock.txt", "investigation.json", ".gitignore",
             "PROJECT_STATE.md", "EXPERIMENT_LOG.md", "FINDINGS.md", "OPEN_QUESTIONS.md",
             ".gitattributes", "CITATION.cff", "SECURITY.md"]:
    files.add(ROOT / name)
files.update((ROOT / "data").glob("*.json"))
token_pattern = re.compile(rb"eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}")
signed_url_pattern = re.compile(rb'''https?://[^\s"'<>]+[?&](?:Signature|Key-Pair-Id)=[A-Za-z0-9_~-]+''')
for path in files:
    if path.suffix.lower() in {".json", ".csv", ".md", ".py", ".toml", ".js", ".jsx", ".html", ".txt", ".mjs"}:
        content = path.read_bytes()
        if token_pattern.search(content) or signed_url_pattern.search(content):
            raise ValueError(f"Credential/signed-link pattern in export: {path.relative_to(ROOT)}")
with ZipFile(destination, "w", ZIP_DEFLATED, compresslevel=6) as archive:
    for path in sorted(files):
        archive.write(path, str(Path("methane_hunter_research") / path.relative_to(ROOT)))
with ZipFile(destination) as archive:
    if archive.testzip() is not None:
        raise RuntimeError("Archive integrity failed")
    if any("/data/raw/" in name or "/.venv/" in name or name.endswith((".env", ".netrc")) for name in archive.namelist()):
        raise RuntimeError("Excluded raw/credential content entered the archive")
print(json.dumps({"path": str(destination), "files": len(files), "bytes": destination.stat().st_size,
                  "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(), "raw_data_included": False}, indent=2))
