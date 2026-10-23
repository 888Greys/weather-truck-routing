"""Spherical geometry helpers.

Everything here is pure and unit-tested. Distances are statute miles and
bearings are degrees clockwise from north, which matches how the US-centric
weather thresholds in the brief are expressed.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from typing import Iterable, Sequence

EARTH_RADIUS_MILES = 3958.7613


@dataclass(frozen=True, slots=True)
class Point:
    lat: float
    lon: float

    def rounded(self, digits: int = 3) -> "Point":
        return Point(round(self.lat, digits), round(self.lon, digits))

    def as_list(self) -> list[float]:
        return [round(self.lat, 5), round(self.lon, 5)]


def haversine_miles(a: Point, b: Point) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(min(1.0, h)))


def cumulative_distances(points: Sequence[Point]) -> list[float]:
    """Distance from the origin to each vertex, in miles."""
    if not points:
        return []
    out = [0.0]
    for prev, cur in zip(points, points[1:]):
        out.append(out[-1] + haversine_miles(prev, cur))
    return out


def point_at_distance(points: Sequence[Point], cumulative: Sequence[float], miles: float) -> Point:
    """Linearly interpolate a position along the polyline."""
    if not points:
        raise ValueError("empty polyline")
    if miles <= 0:
        return points[0]
    if miles >= cumulative[-1]:
        return points[-1]
    idx = bisect.bisect_right(cumulative, miles) - 1
    idx = max(0, min(idx, len(points) - 2))
    span = cumulative[idx + 1] - cumulative[idx]
    if span <= 0:
        return points[idx]
    t = (miles - cumulative[idx]) / span
    a, b = points[idx], points[idx + 1]
    return Point(a.lat + (b.lat - a.lat) * t, a.lon + (b.lon - a.lon) * t)


def bearing_degrees(a: Point, b: Point) -> float:
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlon = math.radians(b.lon - a.lon)
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def destination_point(origin: Point, bearing: float, miles: float) -> Point:
    """Great-circle destination from a start point, bearing and distance."""
    angular = miles / EARTH_RADIUS_MILES
    brg = math.radians(bearing)
    lat1, lon1 = math.radians(origin.lat), math.radians(origin.lon)
    lat2 = math.asin(math.sin(lat1) * math.cos(angular) + math.cos(lat1) * math.sin(angular) * math.cos(brg))
    lon2 = lon1 + math.atan2(
        math.sin(brg) * math.sin(angular) * math.cos(lat1),
        math.cos(angular) - math.sin(lat1) * math.sin(lat2),
    )
    return Point(math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180)


def offset_waypoint(points: Sequence[Point], cumulative: Sequence[float], fraction: float, offset_miles: float) -> Point:
    """A waypoint beside the route, used to synthesise alternative corridors."""
    total = cumulative[-1] if cumulative else 0.0
    base = point_at_distance(points, cumulative, total * fraction)
    ahead = point_at_distance(points, cumulative, min(total, total * fraction + 5.0))
    behind = point_at_distance(points, cumulative, max(0.0, total * fraction - 5.0))
    bearing = bearing_degrees(behind, ahead)
    return destination_point(base, (bearing + 90) % 360, offset_miles)


def sample_along_route(
    points: Sequence[Point],
    spacing_miles: float,
    max_samples: int = 400,
) -> list[tuple[float, Point]]:
    """Checkpoints every `spacing_miles` along the polyline, always including both ends."""
    if not points:
        return []
    if spacing_miles <= 0:
        raise ValueError("spacing_miles must be positive")
    cumulative = cumulative_distances(points)
    total = cumulative[-1]
    if total <= 0:
        return [(0.0, points[0])]

    count = int(total // spacing_miles)
    distances = [i * spacing_miles for i in range(count + 1)]
    if total - distances[-1] > 1e-6:
        distances.append(total)
    # Guard against pathological input (a 40 000 mile route at 1 mile spacing).
    if len(distances) > max_samples:
        step = len(distances) / max_samples
        picked = [distances[min(len(distances) - 1, int(i * step))] for i in range(max_samples)]
        picked[-1] = total
        distances = sorted(set(picked))
    return [(d, point_at_distance(points, cumulative, d)) for d in distances]


def simplify(points: Sequence[Point], max_points: int = 1200) -> list[Point]:
    """Uniform downsample; cheap and good enough for map polylines."""
    if len(points) <= max_points:
        return list(points)
    step = (len(points) - 1) / (max_points - 1)
    picked = [points[min(len(points) - 1, round(i * step))] for i in range(max_points)]
    picked[0], picked[-1] = points[0], points[-1]
    return picked


def dedupe_points(points: Iterable[Point], digits: int = 3) -> list[Point]:
    seen: dict[tuple[float, float], Point] = {}
    for p in points:
        seen.setdefault((round(p.lat, digits), round(p.lon, digits)), p)
    return list(seen.values())
