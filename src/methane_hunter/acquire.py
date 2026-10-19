"""Reacquire frozen Carbon Mapper inputs without persisting signed asset URLs."""
from pathlib import Path
from urllib.parse import urlsplit
import json
import requests

from .data import DownloadBudget, clean_url, sha256, utc_now, write_json

CM_API = "https://api.carbonmapper.org/api/v1"


def sanitize(value):
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        return clean_url(value)
    return value


def read_api(endpoint, params):
    response = requests.get(CM_API + endpoint, params=params, timeout=(15, 90))
    response.raise_for_status()
    return response.json()


def fetch_selected(root="."):
    root = Path(root)
    selection = json.loads((root / "data/metadata/carbonmapper_selection.json").read_text())
    budget = DownloadBudget(root / "data/download_ledger.json")
    stac = json.loads((root / "data/metadata/carbonmapper_stac.json").read_text())
    items = {x["id"]: x for x in stac["features"]}
    manifest = []
    for scene in selection["scenes"]:
        name = scene["name"]
        item = items[name]
        record = {"scene": scene, "stac_id": name, "properties": item["properties"],
                  "files": {}, "source": "Carbon Mapper / EMIT", "accessed_at": utc_now()}
        for key, asset in [("enhancement", "cmf.tif"), ("uncertainty", "uncertainty.tif")]:
            if asset not in item["assets"]:
                record["files"][key] = None
                continue
            obj = item["assets"][asset]
            dest = root / "data/raw" / name / asset
            # Canonical API asset route issues its own current public redirect.
            entry = budget.fetch(obj["href"], dest)
            # STAC file:checksum 0x11 0x14 is SHA1 multihash, not SHA256.
            checksum = obj.get("file:checksum", "")
            if checksum.startswith("1114") and len(checksum) == 44:
                import hashlib
                if hashlib.sha1(dest.read_bytes()).hexdigest() != checksum[4:]:
                    raise ValueError(f"Provider checksum mismatch: {name} {asset}")
            record["files"][key] = {"path": str(dest.relative_to(root)),
                                     "sha256": entry["sha256"], "bytes": dest.stat().st_size,
                                     "url": clean_url(obj["href"]),
                                     "provider_checksum": checksum}
        params = {"scene_name": name, "plume_gas": "CH4", "limit": 500, "offset": 0}
        catalog = read_api("/catalog/plumes/annotated", params)
        rows = catalog.get("items", [])
        # This query covers the selected scene, including sources beyond the ROI.
        if len(rows) == 500:
            raise RuntimeError("Scene catalog needs pagination; cannot claim complete")
        record["catalog"] = {"endpoint": CM_API + "/catalog/plumes/annotated",
                             "parameters": params, "retrieved_at": utc_now(),
                             "response": sanitize(catalog)}
        manifest.append(record)
        write_json(root / "data/input_manifest.json", manifest)
        print(f"Acquired {len(manifest)}/{len(selection['scenes'])}: {name}; {budget.used:,} bytes", flush=True)
    return manifest


def verify_manifest(root="."):
    root = Path(root)
    manifest = json.loads((root / "data/input_manifest.json").read_text())
    for record in manifest:
        for obj in record["files"].values():
            if obj and sha256(root / obj["path"]) != obj["sha256"]:
                raise ValueError(f"Frozen input was modified: {obj['path']}")
    return manifest
