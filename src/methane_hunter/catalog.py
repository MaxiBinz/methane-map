"""Geodesic and temporal association with a finite catalog snapshot.

A match documents an association, not independent confirmation. A missing match
does not establish novelty; catalogs differ in coverage and publication delay.
Coordinates represent a supplied catalog point, which may be a source estimate
rather than an enhancement centroid. Match tolerances must be reported.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import math
from typing import Iterable

from pyproj import Geod

_GEOD = Geod(ellps="WGS84")


def _utc(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    result = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Catalog comparison requires timezone-aware timestamps")
    return result.astimezone(timezone.utc)


def _validate_point(lon: float, lat: float):
    if not math.isfinite(lon) or not math.isfinite(lat) or not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise ValueError("Coordinates must be finite WGS84 longitude/latitude")


@dataclass(frozen=True)
class CatalogRecord:
    catalog_id: str
    longitude: float
    latitude: float
    observed_at: str | datetime | None = None
    source: str = "unspecified"
    granule_id: str | None = None


@dataclass(frozen=True)
class CatalogMatch:
    catalog_id: str
    source: str
    distance_m: float
    time_difference_seconds: float | None
    association: str
    granule_id: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def match_catalog(
    longitude: float,
    latitude: float,
    observed_at: str | datetime,
    records: Iterable[CatalogRecord],
    *,
    distance_m: float = 500.0,
    time_tolerance_seconds: float = 120.0,
) -> list[CatalogMatch]:
    """Return nearby points with explicit spacetime or spatial-only association.

    WGS84 ellipsoidal distances avoid degree-as-meter errors. Timestamp matching
    is necessary even for a persistent emitting source. Unknown catalog times
    are retained as spatial-only associations. Out-of-tolerance observations at
    a nearby source are not treated as the same detection.
    """
    _validate_point(longitude, latitude)
    if not math.isfinite(distance_m) or distance_m <= 0:
        raise ValueError("distance_m must be positive and finite")
    if not math.isfinite(time_tolerance_seconds) or time_tolerance_seconds < 0:
        raise ValueError("time_tolerance_seconds must be nonnegative and finite")
    observation = _utc(observed_at)
    if observation is None:
        raise ValueError("observed_at is required")
    matches = []
    for record in records:
        _validate_point(record.longitude, record.latitude)
        _, _, distance = _GEOD.inv(longitude, latitude, record.longitude, record.latitude)
        if distance > distance_m:
            continue
        catalog_time = _utc(record.observed_at)
        delta = abs((observation - catalog_time).total_seconds()) if catalog_time else None
        association = "spacetime" if delta is not None and delta <= time_tolerance_seconds else "spatial_only"
        matches.append(CatalogMatch(record.catalog_id, record.source, float(distance), delta,
                                    association, record.granule_id))
    return sorted(matches, key=lambda match: (match.association != "spacetime", match.distance_m, match.catalog_id))
