"""Geospatial association fixtures; not observational confirmation."""
import numpy as np
from rasterio.transform import from_origin
from shapely.geometry import box
from methane_hunter.analysis import component_geometry, polygon_catalog_matches


def test_component_polygon_preserves_pixel_coordinates():
    labels = np.zeros((4, 5), dtype="int32")
    labels[1:3, 2:4] = 1
    geom = component_geometry(labels, 1, from_origin(-104, 33, .001, .001), "EPSG:4326")
    assert np.allclose(geom.bounds, [-103.998, 32.997, -103.996, 32.999])


def test_geometry_association_separates_time_and_distance():
    geometry = box(-104.001, 31.999, -103.999, 32.001)
    catalog = [{"gas": "CH4", "plume_id": "known", "id": "known-uuid",
                "geometry_json": {"coordinates": [-104, 32]}, "scene_timestamp": "2024-01-01T12:00:00Z"}]
    same = polygon_catalog_matches(geometry, "2024-01-01T12:00:00Z", catalog)
    assert same[0]["point_to_component_distance_m"] == 0
    assert same[0]["association"] == "same_acquisition_neighborhood"
    assert polygon_catalog_matches(geometry, "2024-01-02T12:00:00Z", catalog)[0]["association"] == "spatial_other_date"
    assert not polygon_catalog_matches(box(-103.9, 32, -103.899, 32.001), "2024-01-01T12:00:00Z", catalog)
