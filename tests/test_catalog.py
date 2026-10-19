"""Synthetic point/timestamp fixtures test association, not methane evidence."""

import pytest

from methane_hunter.catalog import CatalogRecord, match_catalog


def test_temporally_distinct_nearby_source_is_not_same_detection():
    records = [CatalogRecord("same", -103., 32., "2023-01-01T12:00:30Z", "NASA"),
               CatalogRecord("other-date", -103., 32., "2023-01-02T12:00:00Z", "NASA"),
               CatalogRecord("unknown-time", -103., 32., None, "NASA")]
    result = match_catalog(-103., 32., "2023-01-01T12:00:00Z", records)
    by_id = {match.catalog_id: match for match in result}
    assert by_id["same"].association == "spacetime"
    assert by_id["same"].time_difference_seconds == 30
    assert by_id["other-date"].association == "spatial_only"
    assert by_id["unknown-time"].association == "spatial_only"
    assert by_id["unknown-time"].time_difference_seconds is None


def test_geodesic_distances_are_in_meters_and_far_points_excluded():
    records = [CatalogRecord("close", -103., 32.001, "2023-01-01T12:00:00Z"),
               CatalogRecord("far", -103., 33., "2023-01-01T12:00:00Z")]
    matches = match_catalog(-103., 32., "2023-01-01T12:00:00Z", records)
    assert len(matches) == 1
    assert 110 < matches[0].distance_m < 112


def test_timezone_conversion_and_antimeridian():
    records = [CatalogRecord("wrap", -179.999, 0., "2023-01-01T14:00:00+02:00")]
    result = match_catalog(179.999, 0., "2023-01-01T12:00:00Z", records)
    assert result[0].association == "spacetime"
    assert 222 < result[0].distance_m < 223


def test_naive_times_and_invalid_coordinates_are_rejected():
    with pytest.raises(ValueError, match="timezone"):
        match_catalog(-103., 32., "2023-01-01T12:00:00", [])
    with pytest.raises(ValueError, match="Coordinates"):
        match_catalog(-103., 92., "2023-01-01T12:00:00Z", [])


def test_no_catalog_match_does_not_create_a_match():
    assert match_catalog(-103., 32., "2023-01-01T12:00:00Z", []) == []
