"""Synthetic geometry fixtures test association logic, not plume validation."""

from copy import deepcopy

import pytest
from pyproj import Transformer
from shapely.geometry import MultiPolygon, Polygon, box, mapping
from shapely.ops import transform

from methane_hunter.nasa_catalog import (
    NASA_PLM_DOI, cmr_polygon_geometry, load_nasa_catalog, match_nasa_catalog,
)


def _ring(geometry):
    return " ".join(f"{latitude} {longitude}" for longitude, latitude in geometry.exterior.coords)


def _granule(geometry=None, *, suffix="000001", observed_at="2024-08-23T17:34:10Z"):
    geometry = geometry if geometry is not None else box(-104.01, 31.99, -103.99, 32.01)
    return {
        "title": f"EMIT_L2B_CH4PLM_002_20240823T173410_{suffix}",
        "time_start": observed_at,
        "id": f"G{suffix}-LPCLOUD",
        "polygons": [[_ring(geometry)]],
    }


def _catalog(*granules):
    return load_nasa_catalog({"items": list(granules), "pagination_complete": True})


def test_cmr_lat_lon_is_reversed_to_shapely_lon_lat():
    geometry = cmr_polygon_geometry(_granule())
    assert geometry.bounds == (-104.01, 31.99, -103.99, 32.01)
    # Silently accepting a longitude/latitude ring as CMR would swap axes.
    bad = _granule()
    bad["polygons"] = [["-104 32 -103 32 -103 33 -104 32"]]
    with pytest.raises(ValueError, match="latitude then longitude"):
        cmr_polygon_geometry(bad)


def test_separate_cmr_exteriors_make_multipolygon():
    granule = _granule()
    granule["polygons"].append([_ring(box(-103.9, 32.0, -103.89, 32.01))])
    result = cmr_polygon_geometry(granule)
    assert isinstance(result, MultiPolygon)
    assert len(result.geoms) == 2
    assert len(match_nasa_catalog(box(-103.899, 32.001, -103.891, 32.009),
                                  granule["time_start"], _catalog(granule))) == 1


def test_holes_or_ambiguous_ring_groups_fail_closed():
    granule = _granule()
    granule["polygons"][0].append(_ring(box(-104.001, 31.999, -103.999, 32.001)))
    with pytest.raises(ValueError, match="rings/holes"):
        cmr_polygon_geometry(granule)


@pytest.mark.parametrize("polygons", [
    [], [["32 -104 32 -103 33 -103"]], [["32 -104 32 -103 33 -103 32"]],
    [["32 -104 32 -103 nan -103 32 -104"]],
    [["32 -104 33 -103 32 -103 33 -104 32 -104"]],
])
def test_missing_open_malformed_or_invalid_polygons_are_rejected(polygons):
    granule = _granule()
    granule["polygons"] = polygons
    with pytest.raises(ValueError):
        cmr_polygon_geometry(granule)


def test_no_bounding_box_fallback_even_if_cmr_boxes_are_available():
    granule = _granule()
    del granule["polygons"]
    granule["boxes"] = ["31 -105 33 -103"]
    with pytest.raises(ValueError, match="no bounding-box fallback"):
        cmr_polygon_geometry(granule)


def test_snapshot_requires_complete_pagination_and_exact_id_timestamp():
    with pytest.raises(ValueError, match="pagination"):
        load_nasa_catalog({"items": [_granule()], "pagination_complete": False})
    with pytest.raises(ValueError, match="exact acquisition timestamp"):
        _catalog(_granule(observed_at="2024-08-23T17:34:11Z"))
    with pytest.raises(ValueError, match="timezone-aware"):
        _catalog(_granule(observed_at="2024-08-23T17:34:10"))


def test_matching_requires_positive_polygon_area_not_crop_bbox_overlap():
    # Candidate is inside a broad crop bbox but outside its narrow triangle.
    triangle = Polygon([(-104.02, 32), (-104, 32), (-104.02, 32.02), (-104.02, 32)])
    records = _catalog(_granule(triangle))
    candidate = box(-104.006, 32.014, -104.002, 32.018)
    assert candidate.intersects(box(*triangle.bounds))
    assert not match_nasa_catalog(candidate, "2024-08-23T17:34:10Z", records)
    # Exact edge contact is not positive observed area.
    assert not match_nasa_catalog(box(-104.04, 32, -104.02, 32.01),
                                  "2024-08-23T17:34:10Z", records)


def test_overlap_fraction_uses_projected_metre_area_and_serializable_evidence():
    official = box(-104.01, 31.99, -103.99, 32.01)
    candidate = box(-104.02, 31.99, -104, 32.01)
    records = _catalog(_granule(official))
    matches = match_nasa_catalog(mapping(candidate), "2024-08-23T17:34:10Z", records)
    assert len(matches) == 1
    result = matches[0]
    projected = Transformer.from_crs(4326, 32613, always_xy=True).transform
    p_candidate = transform(projected, candidate)
    expected_overlap = transform(projected, candidate.intersection(official)).area
    assert result.overlap_area_m2 == pytest.approx(expected_overlap)
    assert result.overlap_area_m2 > 1_000_000
    assert result.candidate_overlap_fraction == pytest.approx(expected_overlap / p_candidate.area)
    evidence = result.to_dict()
    assert evidence["doi"] == NASA_PLM_DOI
    assert evidence["area_crs"] == "EPSG:32613"
    assert evidence["independent_corroboration"] is False


def test_time_tolerance_is_inclusive_and_observation_must_be_aware():
    records = _catalog(_granule())
    candidate = box(-104.005, 31.995, -103.995, 32.005)
    assert match_nasa_catalog(candidate, "2024-08-23T17:36:10Z", records)[0].time_difference_seconds == 120
    assert not match_nasa_catalog(candidate, "2024-08-23T17:36:11Z", records)
    assert match_nasa_catalog(candidate, "2024-08-23T19:34:10+02:00", records)[0].time_difference_seconds == 0
    with pytest.raises(ValueError, match="timezone-aware"):
        match_nasa_catalog(candidate, "2024-08-23T17:34:10", records)


def test_duplicate_ids_deduplicate_and_conflicts_fail_closed():
    granule = _granule()
    assert len(_catalog(granule, deepcopy(granule))) == 1
    conflicting = _granule(box(-104.1, 32, -104.09, 32.01))
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        _catalog(granule, conflicting)


def test_utm13_area_of_use_and_nondegenerate_candidate_are_required():
    with pytest.raises(ValueError, match="area of use"):
        match_nasa_catalog(box(0, 30, 1, 31), "2024-08-23T17:34:10Z", [])
    with pytest.raises(ValueError, match="positive area"):
        match_nasa_catalog(Polygon(), "2024-08-23T17:34:10Z", [])
    with pytest.raises(ValueError, match="nonnegative"):
        match_nasa_catalog(box(-104.1, 32, -104, 32.1), "2024-08-23T17:34:10Z", [],
                           time_tolerance_seconds=-1)
