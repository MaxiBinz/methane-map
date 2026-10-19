"""Authenticated acquisition with an in-memory Earthdata bearer token."""
from pathlib import Path
import getpass
import json
import os
from urllib.parse import urlsplit

import requests
from .data import DownloadBudget, clean_url, utc_now, write_json


def fetch_nasa_selected(root=".", token=None):
    root = Path(root)
    selection = json.loads((root / "data/metadata/nasa_selection.json").read_text())
    if len(selection["scenes"]) > 20:
        raise ValueError("Initial investigation is limited to 20 full scenes")
    token = token or os.environ.get("EARTHDATA_TOKEN") or getpass.getpass("Earthdata token (hidden input): ")
    session = requests.Session()
    session.headers["Authorization"] = "Bearer " + token
    other_bytes = 32  # recorded access-check read
    for file in (root / "data").glob("*download_ledger.json"):
        if file.name == "nasa_download_ledger.json":
            continue
        ledger = json.loads(file.read_text())
        other_bytes += (sum(x["transferred_bytes"] for x in ledger)
                        if isinstance(ledger, list) else ledger.get("total_bytes", 0))
    budget = DownloadBudget(root / "data/nasa_download_ledger.json",
                            limit=5_000_000_000 - other_bytes, session=session)
    manifest = []
    try:
        for scene in selection["scenes"]:
            record = {"scene": scene, "source": "NASA EMIT CH4ENH V002", "files": {},
                      "accessed_at": utc_now()}
            for key in ["enhancement", "sensitivity", "uncertainty", "quality"]:
                url = scene["urls"].get(key)
                if not url:
                    record["files"][key] = None
                    continue
                parsed = urlsplit(url)
                if parsed.scheme != "https" or parsed.hostname != "data.lpdaac.earthdatacloud.nasa.gov":
                    raise ValueError("Bearer token may only be sent to the verified NASA data host")
                path = root / "data/raw/nasa" / scene["name"] / Path(parsed.path).name
                entry = budget.fetch(url, path)
                record["files"][key] = {"path": str(path.relative_to(root)), "sha256": entry["sha256"],
                                         "bytes": path.stat().st_size, "url": clean_url(url)}
            manifest.append(record)
            write_json(root / "data/nasa_input_manifest.json", manifest)
            print(f"Acquired NASA {len(manifest)}/{len(selection['scenes'])}: {scene['name']}; {budget.used:,} data bytes", flush=True)
    finally:
        session.headers.pop("Authorization", None)
        session.close()
        del token
    return manifest

