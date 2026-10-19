"""Inspect publishable Git files without printing credential values.

Run --staged before a commit or --tracked in CI. This is a bounded pattern scan,
not a guarantee that every possible secret encoding can be recognized.
"""
from pathlib import Path
import argparse
import io
import json
import re
import subprocess
import sys
from zipfile import ZipFile, is_zipfile

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "JWT credential": rb"eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}",
    "GitHub credential": rb"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})",
    "AWS access key": rb"(?:AKIA|ASIA)[A-Z0-9]{16}",
    "private key": rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "literal bearer credential": rb"Bearer[ \t]+[A-Za-z0-9_-]{40,}",
    "signed access URL": rb"[?&](?:Signature|Key-Pair-Id|X-Amz-Signature)=",
    "local dependency path": rb"^(?:[A-Za-z0-9_.-]+[ \t]+@[ \t]+file://|-e[ \t]+/(?:Users|home|private|var)/)",
}
FORBIDDEN_PARTS = {".venv", "node_modules", "__pycache__", ".pytest_cache", ".data-app-offline"}


def scan_bytes(name, content):
    findings = []
    for kind, pattern in PATTERNS.items():
        if re.search(pattern, content, re.MULTILINE):
            findings.append({"file": name, "kind": kind})
    if content[:4] == b"PK\x03\x04" and is_zipfile(io.BytesIO(content)):
        with ZipFile(io.BytesIO(content)) as archive:
            if sum(i.file_size for i in archive.infolist()) > 100_000_000:
                findings.append({"file": name, "kind": "archive exceeds inspection limit"})
            else:
                for item in archive.infolist():
                    findings.extend(scan_bytes(f"{name}!{item.filename}", archive.read(item)))
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged", action="store_true")
    group.add_argument("--tracked", action="store_true")
    args = parser.parse_args()
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    findings = []
    size = 0
    for name in filter(None, names):
        p = Path(name)
        if (FORBIDDEN_PARTS.intersection(p.parts) or name.startswith("data/raw/")
                or p.name in {".env", ".netrc"} or p.suffix in {".key", ".pem"}):
            findings.append({"file": name, "kind": "excluded private/generated path"})
        content = (subprocess.check_output(["git", "show", f":{name}"], cwd=ROOT)
                   if args.staged else (ROOT / name).read_bytes())
        size += len(content)
        if len(content) >= 50_000_000:
            findings.append({"file": name, "kind": "unexpected large file"})
        findings.extend(scan_bytes(name, content))
    print(json.dumps({"status": "fail" if findings else "pass", "files": len(list(filter(None, names))),
                      "bytes": size, "findings": findings}, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
