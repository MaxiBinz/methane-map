"""Read a token with terminal echo disabled; never store or print it."""
import getpass
import json
import requests
from pathlib import Path
from urllib.parse import urlparse

token = getpass.getpass("Earthdata token (hidden input): ")
scene = json.loads(Path("data/metadata/cmr_enh_granules.json").read_text())["feed"]["entry"][-1]
url = next(x["href"] for x in scene["links"] if x.get("href", "").endswith(".tif") and x["href"].startswith("https://data.lpdaac.earthdatacloud.nasa.gov/"))
with requests.get(url, headers={"Authorization": "Bearer " + token, "Range": "bytes=0-31"}, stream=True, timeout=60) as r:
    result = {"http_status": r.status_code, "content_type": r.headers.get("Content-Type"),
              "host": urlparse(url).hostname, "scene": scene["producer_granule_id"]}
    if r.ok:
        first = next(r.iter_content(32))
        result["tiff_magic_valid"] = first[:4] in [b"II*\x00", b"MM\x00*", b"II+\x00"]
        result["sample_bytes_read"] = len(first)
    Path("data/metadata/earthdata_access_check.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
del token
