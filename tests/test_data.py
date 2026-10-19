"""Software fixtures only; these tests do not establish scientific sensitivity."""
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from methane_hunter.data import DownloadBudget, aligned_rasters, clean_url


def test_redacts_sensitive_url_components():
    assert clean_url("https://user:pass@example.org/file.tif?token=secret#x") == "https://example.org/file.tif"


def write_tif(path, x=0):
    with rasterio.open(path, "w", driver="GTiff", height=4, width=4, count=1,
                       dtype="float32", crs="EPSG:4326", nodata=-9999,
                       transform=from_origin(x, 1, .001, .001)) as ds:
        arr = np.ones((4, 4), dtype="float32")
        arr[0, 0] = -9999
        ds.write(arr, 1)


def test_alignment_and_nodata(tmp_path):
    a, b = tmp_path / "enh.tif", tmp_path / "sens.tif"
    write_tif(a)
    write_tif(b, x=.001)
    arrays, _ = aligned_rasters(a)
    assert np.isnan(arrays["enhancement"][0, 0])
    assert arrays["uncertainty"] is None
    with pytest.raises(ValueError, match="misaligned"):
        aligned_rasters(a, sensitivity=b)


class FakeResponse:
    headers = {"Content-Type": "image/tiff"}
    status_code = 200

    def __enter__(self): return self
    def __exit__(self, *args): pass
    def raise_for_status(self): pass
    def iter_content(self, _):
        yield b"1234"
        yield b"5678"


class FakeSession:
    def get(self, *args, **kwargs): return FakeResponse()


def test_stream_budget_counts_partial_and_removes_file(tmp_path):
    budget = DownloadBudget(tmp_path / "ledger.json", limit=5, session=FakeSession())
    dest = tmp_path / "a.tif"
    with pytest.raises(RuntimeError, match="budget"):
        budget.fetch("https://example.org/a.tif", dest)
    assert budget.used == 8  # count bytes received even when the over-limit chunk is discarded
    assert not dest.exists()
    assert not dest.with_name("a.tif.part").exists()
    assert budget.entries[0]["status"] == "failed"


def test_hash_guard_blocks_modified_cache(tmp_path):
    budget = DownloadBudget(tmp_path / "ledger.json", limit=20, session=FakeSession())
    dest = tmp_path / "a.tif"
    budget.fetch("https://example.org/a.tif", dest)
    budget.fetch("https://example.org/a.tif", dest)  # no transfer
    assert budget.used == 8
    dest.write_bytes(b"modified")
    with pytest.raises(ValueError, match="modified"):
        budget.fetch("https://example.org/a.tif", dest)


def test_reacquisition_checks_original_hash_after_cache_is_deleted(tmp_path):
    budget = DownloadBudget(tmp_path / "ledger.json", limit=40, session=FakeSession())
    dest = tmp_path / "a.tif"
    budget.fetch("https://example.org/a.tif", dest)
    dest.unlink()
    class ChangedResponse(FakeResponse):
        def iter_content(self, _):
            yield b"changed"
    class ChangedSession:
        def get(self, *args, **kwargs): return ChangedResponse()
    budget.session = ChangedSession()
    with pytest.raises(ValueError, match="frozen input hash"):
        budget.fetch("https://example.org/a.tif", dest)
    assert not dest.exists()
    assert budget.entries[-1]["status"] == "failed"
