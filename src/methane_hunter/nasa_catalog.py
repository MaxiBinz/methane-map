"""Associate candidates with published EMIT V002 CMR plume polygons.

These are same-instrument catalog associations, never independent satellite
corroboration. CMR ``polygons`` coordinate strings use latitude, longitude;
Shapely geometries use longitude, latitude. Raster crop bounding boxes are not
substituted for the published outline.

The supported CMR response layout is a list of polygon groups, each containing
one exterior-ring string. Multiple singleton groups become a MultiPolygon.
Multi-ring groups are rejected because their exterior/hole semantics are not
established here. Invalid outlines are rejected without geometry repair.
Association areas are restricted to UTM zone 13N, appropriate to this project's
fixed Permian Basin region; this is not a global area-estimation API.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from typing import Iterable, Mapping

import numpy as np
from pyproj import Transformer
from shapely import transform
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.geometry.base import BaseGeometry


NASA_PLM_DOI = "https://doi.org/10.5067/EMIT/EMITL2BCH4PLM.002"
_GRANULE_ID = re.compile(r"^EMIT_L2B_CH4PLM_002_(\d{8}T\d{6})_\d+$")
_TO_UTM13 = Transformer.from_crs("EPSG:4326", "EPSG:32613", always_xy=True)


def _utc(value: str | datetime) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if not isinstance(result, datetime) or result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("NASA catalog association requires timezone-aware timestamps")
    return result.astimezone(timezone.utc)


def _polygonal(geometry: BaseGeometry) -> BaseGeometry:
    if not isinstance(geometry, (Polygon, MultiPolygon)):
        raise ValueError("A nonempty Polygon or MultiPolygon is required")
    if geometry.is_empty or not geometry.is_valid or geometry.area <= 0:
        raise ValueError("Polygon geometry must be nonempty, valid, and have positive area")
    minx, miny, maxx, maxy = geometry.bounds
    if (not all(math.isfinite(v) for v in geometry.bounds)
            or minx < -180 or maxx > 180 or miny < -90 or maxy > 90):
        raise ValueError("Polygon coordinates must be finite WGS84 longitude/latitude")
    return geometry


def cmr_polygon_geometry(granule: Mapping) -> Polygon | MultiPolygon:
    """Read exact CMR outline vertices, reversing explicit lat/lon pairs.

    Missing polygons, open rings, degenerate rings, self-intersections, and
    ambiguous nested rings fail closed. ``boxes`` and browse/STAC crop extents
    are intentionally ignored, even when an exact outline is absent.
    """
    groups = granule.get("polygons")
    if not isinstance(groups, list) or not groups:
        raise ValueError("CMR precise polygons are required; no bounding-box fallback")
    polygons = []
    for group in groups:
        if not isinstance(group, list) or len(group) != 1 or not isinstance(group[0], str):
            raise ValueError("Ambiguous CMR polygon rings/holes: require one exterior ring per group")
        try:
            values = [float(value) for value in group[0].split()]
        except ValueError as exc:
            raise ValueError("CMR polygon ring contains nonnumeric coordinates") from exc
        if len(values) < 8 or len(values) % 2:
            raise ValueError("CMR polygon needs at least four closed latitude/longitude pairs")
        coordinates = []
        for latitude, longitude in zip(values[::2], values[1::2]):
            if (not math.isfinite(latitude) or not math.isfinite(longitude)
                    or not -90 <= latitude <= 90 or not -180 <= longitude <= 180):
                raise ValueError("CMR coordinates must be finite latitude then longitude")
            coordinates.append((longitude, latitude))
        if coordinates[0] != coordinates[-1]:
            raise ValueError("CMR exterior ring must be explicitly closed")
        polygon = Polygon(coordinates)
        _polygonal(polygon)
        polygons.append(polygon)
    geometry = polygons[0] if len(polygons) == 1 else MultiPolygon(polygons)
    return _polygonal(geometry)


@dataclass(frozen=True)
class NasaPlumeRecord:
    granule_id: str
    observed_at: str
    geometry: Polygon | MultiPolygon
    cmr_concept_id: str | None = None
    source: str = "NASA EMIT methane plume complexes V002"
    doi: str = NASA_PLM_DOI


@dataclass(frozen=True)
class NasaPlumeMatch:
    catalog_id: str
    granule_id: str
    source: str
    doi: str
    cmr_concept_id: str | None
    observed_at: str
    time_difference_seconds: float
    overlap_area_m2: float
    candidate_overlap_fraction: float
    association: str = "spacetime_precise_polygon_overlap"
    geometry_source: str = "CMR published plume polygon vertices"
    area_crs: str = "EPSG:32613"
    independent_corroboration: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def load_nasa_catalog(snapshot: str | Path | Mapping) -> list[NasaPlumeRecord]:
    """Load the frozen ``nasa_plume_cmr_same_scenes.json`` comparison snapshot.

    The snapshot's pagination must be explicitly complete. Official V002 plume
    granule IDs and their exact acquisition timestamp must agree. Repeated
    records are deduplicated by granule ID; conflicting duplicates are errors.
    """
    if isinstance(snapshot, (str, Path)):
        with Path(snapshot).open() as handle:
            snapshot = json.load(handle)
    if not isinstance(snapshot, Mapping) or snapshot.get("pagination_complete") is not True:
        raise ValueError("NASA catalog snapshot must declare complete pagination")
    items = snapshot.get("items")
    if not isinstance(items, list):
        raise ValueError("NASA catalog snapshot requires an items list")
    records = {}
    for granule in items:
        if not isinstance(granule, Mapping):
            raise ValueError("NASA catalog entries must be CMR granule objects")
        granule_id = granule.get("producer_granule_id") or granule.get("title")
        match = _GRANULE_ID.fullmatch(granule_id) if isinstance(granule_id, str) else None
        if match is None:
            raise ValueError("Official EMIT_L2B_CH4PLM_002 granule ID is required")
        observed = _utc(granule.get("time_start"))
        identifier_time = datetime.strptime(match.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
        if observed != identifier_time:
            raise ValueError("NASA plume granule ID and exact acquisition timestamp disagree")
        record = NasaPlumeRecord(
            granule_id=granule_id,
            observed_at=observed.isoformat().replace("+00:00", "Z"),
            geometry=cmr_polygon_geometry(granule),
            cmr_concept_id=granule.get("id"),
        )
        if granule_id in records:
            existing = records[granule_id]
            if (existing.observed_at != record.observed_at
                    or not existing.geometry.equals(record.geometry)
                    or existing.cmr_concept_id != record.cmr_concept_id):
                raise ValueError("Conflicting duplicate NASA plume granule")
        records[granule_id] = record
    return sorted(records.values(), key=lambda record: (record.observed_at, record.granule_id))


def _project_utm13(geometry: BaseGeometry) -> BaseGeometry:
    _polygonal(geometry)
    minx, miny, maxx, maxy = geometry.bounds
    if minx < -108 or maxx > -102 or miny < 0 or maxy > 84:
        raise ValueError("Area association is restricted to the EPSG:32613 area of use")
    projected = _transform_utm13(geometry)
    if not projected.is_valid or not math.isfinite(projected.area) or projected.area <= 0:
        raise ValueError("Projected polygon must have valid positive area")
    return projected


def _transform_utm13(geometry: BaseGeometry) -> BaseGeometry:
    return transform(geometry, lambda xy: np.column_stack(
        _TO_UTM13.transform(xy[:, 0], xy[:, 1])))


def match_nasa_catalog(
    candidate_geometry: BaseGeometry | Mapping,
    observed_at: str | datetime,
    records: Iterable[NasaPlumeRecord],
    *,
    time_tolerance_seconds: float = 120.0,
) -> list[NasaPlumeMatch]:
    """Return same-acquisition catalog outlines with positive area overlap.

    Inputs are WGS84 polygonal geometries. There is no spatial buffer or
    distance-based fallback: touching boundaries or overlapping crop bounding
    boxes do not establish a match. Time tolerance is inclusive and explicit.
    Fractions use intersection area divided by candidate area in UTM zone 13N.
    Matching all or part of an existing outline establishes a catalog
    association; it does not validate other candidate pixels as methane.
    """
    if not math.isfinite(time_tolerance_seconds) or time_tolerance_seconds < 0:
        raise ValueError("time_tolerance_seconds must be finite and nonnegative")
    if isinstance(candidate_geometry, Mapping):
        candidate_geometry = shape(candidate_geometry)
    candidate_projected = _project_utm13(candidate_geometry)
    observation = _utc(observed_at)
    matches = []
    for record in records:
        delta = abs((observation - _utc(record.observed_at)).total_seconds())
        if delta > time_tolerance_seconds:
            continue
        _project_utm13(record.geometry)
        # Establish topological overlap before projection. Projecting touching
        # boundaries with different vertex spacing can create tiny artificial
        # slivers when straight projected chords no longer coincide exactly.
        geographic_overlap = candidate_geometry.intersection(record.geometry)
        if geographic_overlap.area <= 0:
            continue
        overlap = _transform_utm13(geographic_overlap).area
        if not math.isfinite(overlap) or overlap <= 0:
            raise ValueError("Catalog intersection has invalid projected area")
        matches.append(NasaPlumeMatch(
            catalog_id=record.granule_id,
            granule_id=record.granule_id,
            source=record.source,
            doi=record.doi,
            cmr_concept_id=record.cmr_concept_id,
            observed_at=record.observed_at,
            time_difference_seconds=delta,
            overlap_area_m2=float(overlap),
            candidate_overlap_fraction=float(min(1.0, overlap / candidate_projected.area)),
        ))
    return sorted(matches, key=lambda match: (
        match.time_difference_seconds, -match.candidate_overlap_fraction, match.granule_id))
