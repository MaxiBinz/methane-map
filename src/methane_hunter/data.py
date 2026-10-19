"""Public metadata discovery, bounded downloads, and strict raster alignment.

Downloaded content is cached with hashes. Authentication is optional and explicit;
Earthdata credentials are read only by earthaccess and never written here.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import numpy as np
import rasterio
import requests
from rasterio.warp import transform_bounds


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def clean_url(url):
    """Never retain signed query strings or embedded credentials in provenance."""
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.hostname or "", p.path, "", ""))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


class DownloadBudget:
    """Persistent byte ledger; counts partial and repeated network transfers too.

    Intended for one download process at a time. Do not parallelize writers.
    """
    def __init__(self, ledger, limit=5_000_000_000, session=None):
        self.path = Path(ledger)
        self.limit = limit
        self.session = session or requests.Session()
        self.entries = json.loads(self.path.read_text()) if self.path.exists() else []

    @property
    def used(self):
        return sum(e["transferred_bytes"] for e in self.entries)

    def fetch(self, url, destination, expected_sha256=None):
        dest = Path(destination)
        prior = next((e for e in reversed(self.entries)
                      if e.get("path") == str(dest) and e.get("status") == "ok"), None)
        if expected_sha256 is None and prior:
            expected_sha256 = prior["sha256"]
        if dest.exists():
            existing = prior
            if existing and sha256(dest) == existing["sha256"]:
                if expected_sha256 and existing["sha256"] != expected_sha256:
                    raise ValueError("Cached input differs from the frozen input hash")
                return existing
            raise ValueError(f"Untracked or modified cached file: {dest}")
        if self.used >= self.limit:
            raise RuntimeError("Download budget exhausted")
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        entry = {"url": clean_url(url), "path": str(dest), "started_at": utc_now(),
                 "transferred_bytes": 0, "status": "failed"}
        self.entries.append(entry)
        try:
            with self.session.get(url, stream=True, timeout=(15, 90)) as response:
                entry["http_status"] = response.status_code
                response.raise_for_status()
                mime = response.headers.get("Content-Type", "")
                entry["content_type"] = mime
                if "text/html" in mime:
                    raise RuntimeError("HTML/login response cannot be treated as scientific data")
                length = int(response.headers.get("Content-Length", "0"))
                if length > self.limit - self.used:
                    raise RuntimeError("Content-Length exceeds remaining download budget")
                with part.open("wb") as out:
                    for chunk in response.iter_content(1024 * 256):
                        entry["transferred_bytes"] += len(chunk)
                        if self.used > self.limit:
                            raise RuntimeError("Streaming response exceeds remaining download budget")
                        out.write(chunk)
            digest = sha256(part)
            if expected_sha256 and digest != expected_sha256:
                raise ValueError("Downloaded input differs from the frozen input hash")
            entry.update(sha256=digest, status="ok")
            os.replace(part, dest)
            return entry
        except Exception as exc:
            entry["error"] = type(exc).__name__  # no signed URLs or secrets
            part.unlink(missing_ok=True)
            raise
        finally:
            entry["finished_at"] = utc_now()
            write_json(self.path, self.entries)


def cmr_granules(short_name, bbox, *, version="002", temporal=None,
                 page_size=20, page_num=1, sort_key="start_date", session=None):
    """One explicit CMR page; caller must check CMR-Hits before completeness claims."""
    params = {"short_name": short_name, "version": version,
              "bounding_box": ",".join(map(str, bbox)), "page_size": page_size,
              "page_num": page_num, "sort_key": sort_key}
    if temporal:
        params["temporal"] = temporal
    response = (session or requests).get(
        "https://cmr.earthdata.nasa.gov/search/granules.json", params=params, timeout=60)
    response.raise_for_status()
    return {"retrieved_at": utc_now(), "endpoint": clean_url(response.url),
            "parameters": params, "total_hits": int(response.headers.get("CMR-Hits", 0)),
            "response": response.json()}


def earthdata_session():
    """Use user-configured credentials; no interactive prompt or credential storage."""
    import earthaccess
    auth = earthaccess.login(strategy="environment", persist=False)
    if not auth.authenticated:
        raise RuntimeError("Earthdata credentials unavailable; configure EARTHDATA_USERNAME and EARTHDATA_PASSWORD locally")
    return earthaccess.get_requests_https_session()


def read_raster(path):
    """Read numeric GeoTIFF values and preserve missingness, units, and CRS."""
    with rasterio.open(path) as ds:
        alpha_band = ds.count == 2 and ds.colorinterp[1] == rasterio.enums.ColorInterp.alpha
        if (ds.count != 1 and not alpha_band) or ds.crs is None:
            raise ValueError("Expected one georeferenced science band, optionally with an alpha mask")
        a = ds.read(1, masked=True).astype("float64").filled(np.nan)
        if alpha_band:
            a[ds.read(2) <= 0] = np.nan
        a[~np.isfinite(a)] = np.nan
        meta = {"path": str(path), "shape": list(a.shape), "crs": str(ds.crs),
                "transform": list(ds.transform)[:6], "bounds": list(ds.bounds),
                "bounds_wgs84": list(transform_bounds(ds.crs, "EPSG:4326", *ds.bounds)),
                "nodata": ds.nodata, "units": list(ds.units), "tags": ds.tags(),
                "band_count": ds.count, "color_interpretation": [c.name for c in ds.colorinterp]}
        return a, meta


def aligned_rasters(enhancement, sensitivity=None, uncertainty=None, quality=None):
    """Fail closed on shape/CRS/affine mismatch; never silently resample masks."""
    base, meta = read_raster(enhancement)
    arrays = {"enhancement": base}
    for key, path in [("sensitivity", sensitivity), ("uncertainty", uncertainty), ("quality", quality)]:
        if path is None:
            arrays[key] = None
            continue
        arr, info = read_raster(path)
        for field in ["shape", "crs", "transform"]:
            if info[field] != meta[field]:
                raise ValueError(f"{key} raster {field} is misaligned")
        arrays[key] = arr
    return arrays, meta
