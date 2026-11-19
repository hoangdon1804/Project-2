"""Shared helpers for area-based fake zone metrics.

Used by POST /territories/{id}/fake-zone-metrics (routes.py) and by fake_zone_sales_history.py, so that
both generate data the same way:

    customers = max(MIN_CUSTOMERS, round(density * area_km2 * LogNormal(0, noise)))
    density   = customers_per_km2 if given, else MEDIAN_ZONE_CUSTOMERS / median zone area of the group

so that within a territory the number of customers grows with the zone area, while a zone of median
area gets about MEDIAN_ZONE_CUSTOMERS customers (the same order of magnitude as the old uniform data).
"""
import math
import statistics
from typing import Iterable, Optional, Tuple

from shapely.errors import GEOSException
from shapely.geometry import shape
from shapely.ops import transform
from shapely.validation import make_valid

MEDIAN_ZONE_CUSTOMERS = 200
MIN_CUSTOMERS = 5
DEFAULT_NOISE = 0.25


def area_km2(geometry) -> Optional[float]:
    """Area (km²) of a lon/lat GeoJSON geometry, with a local plane projection around its centroid
    (error well below 1% at ward/commune scale). None when the geometry is missing or invalid."""
    if not geometry:
        return None
    try:
        polygon = shape(geometry)
        if not polygon.is_valid:
            polygon = make_valid(polygon)
        if polygon.is_empty:
            return None
        lat0 = polygon.centroid.y
    except (TypeError, ValueError, KeyError, AttributeError, GEOSException):
        return None
    kx = 111.320 * math.cos(math.radians(lat0))  # km per degree of longitude at lat0
    ky = 110.574  # km per degree of latitude
    area = transform(lambda x, y, z=None: (x * kx, y * ky), polygon).area
    return area if area > 0 else None


def density_for(areas: Iterable[Optional[float]],
                customers_per_km2: Optional[float] = None) -> Tuple[float, float]:
    """(density in customers/km², median area in km²) for a group of zones. Raises ValueError if no area."""
    known = [a for a in areas if a]
    if not known:
        raise ValueError("no zone with a valid geometry")
    median_area = statistics.median(known)
    return (customers_per_km2 or MEDIAN_ZONE_CUSTOMERS / median_area), median_area


def fake_customers(rng, area: float, density: float, noise: float = DEFAULT_NOISE) -> int:
    return max(MIN_CUSTOMERS, round(density * area * rng.lognormvariate(0, noise)))


def fake_orders(rng, customers: int) -> int:
    return rng.randint(max(1, customers // 8), max(2, customers // 2))
