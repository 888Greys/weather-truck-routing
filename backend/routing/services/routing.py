"""Route candidates from OSRM, plus a deterministic synthetic provider.

The public OSRM demo server ignores `alternatives`, so it usually returns a
single route. To still present three real choices we ask OSRM for alternatives
first and, when it cannot supply them, we synthesise corridors by routing
through a waypoint offset perpendicular to the fastest path. Every candidate is
a genuine road route from the same engine - nothing is drawn by hand.
"""
from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from django.conf import settings

from . import geo
from .cache import ROUTE_TTL, memo
from .geo import Point

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RouteCandidate:
    points: list[Point]
    distance_miles: float
    duration_hours: float
    label: str = ""
    source: str = "osrm"
    via: Point | None = None
    tags: list[str] = field(default_factory=list)
    delta_vs_fastest_miles: float = 0.0


def _decode_geometry(payload: dict) -> list[Point]:
    coords = payload.get("geometry", {}).get("coordinates") or []
    return [Point(lat=lat, lon=lon) for lon, lat in coords]


class OsrmRouter:
    provider_name = "osrm"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.OSRM_BASE_URL).rstrip("/")

    def _request(self, waypoints: list[Point], alternatives: bool) -> list[RouteCandidate]:
        from .http import get_json

        coord_string = ";".join(f"{p.lon:.6f},{p.lat:.6f}" for p in waypoints)
        url = f"{self.base_url}/route/v1/driving/{coord_string}"
        payload = get_json(
            url,
            {
                "alternatives": "true" if alternatives else "false",
                "overview": "full",
                "geometries": "geojson",
                "steps": "false",
                "continue_straight": "false",
            },
        )
        if payload.get("code") != "Ok":
            raise ValueError(f"OSRM returned {payload.get('code')}: {payload.get('message')}")
        out = []
        for route in payload.get("routes", []):
            points = _decode_geometry(route)
            if len(points) < 2:
                continue
            out.append(
                RouteCandidate(
                    points=points,
                    distance_miles=route["distance"] / 1609.344,
                    duration_hours=route["duration"] / 3600.0,
                    source="osrm",
                )
            )
        return out

    @staticmethod
    def _too_similar(a: RouteCandidate, b: RouteCandidate) -> bool:
        """Same road if the distance matches within 2% and shapes track closely."""
        if abs(a.distance_miles - b.distance_miles) / max(a.distance_miles, 1e-6) < 0.02:
            return True
        step_a = max(1, len(a.points) // 24)
        step_b = max(1, len(b.points) // 24)
        pa, pb = a.points[::step_a], b.points[::step_b]
        n = min(len(pa), len(pb))
        if n < 2:
            return True
        total = sum(geo.haversine_miles(pa[i], pb[i]) for i in range(n)) / n
        return total < 2.0

    def plan(self, origin: Point, destination: Point, count: int = 3) -> list[RouteCandidate]:
        return memo(
            "routes",
            {
                "o": (round(origin.lat, 4), round(origin.lon, 4)),
                "d": (round(destination.lat, 4), round(destination.lon, 4)),
                "count": count,
                "provider": self.provider_name,
            },
            ROUTE_TTL,
            lambda: self._plan_uncached(origin, destination, count),
        )

    def _plan_uncached(self, origin: Point, destination: Point, count: int) -> list[RouteCandidate]:
        try:
            candidates = self._request([origin, destination], alternatives=True)
        except Exception as exc:  # noqa: BLE001 - degrade to via-point strategies
            logger.warning("OSRM base route failed: %s", exc)
            raise

        base = min(candidates, key=lambda c: c.duration_hours)
        cumulative = geo.cumulative_distances(base.points)

        # Detour strategies are independent, so they run concurrently: on a cold
        # cache the difference is ~6 s of sequential OSRM calls vs ~1 s.
        # Four well-spread detours: enough to find two distinct corridors, few
        # enough to resolve in a single parallel round against the demo server.
        strategies = [
            (0.35, 12.0),
            (0.65, -12.0),
            (0.50, 30.0),
            (0.30, -26.0),
        ]
        vias = [geo.offset_waypoint(base.points, cumulative, f, o) for f, o in strategies]

        def attempt(via: Point) -> RouteCandidate | None:
            try:
                routes = self._request([origin, via, destination], alternatives=False)
            except Exception as exc:  # noqa: BLE001 - a dead detour is not fatal
                logger.info("Via-point route failed: %s", exc)
                return None
            for route in routes:
                if route.distance_miles <= base.distance_miles * 2.2:
                    route.via = via
                    route.source = "osrm:via"
                    return route
            return None

        with ThreadPoolExecutor(max_workers=min(4, len(vias))) as pool:
            detours = [r for r in pool.map(attempt, vias) if r is not None]

        for detour in detours:
            if len(candidates) >= count:
                break
            if any(self._too_similar(detour, existing) for existing in candidates):
                continue
            candidates.append(detour)

        if len(candidates) < 2:
            raise ValueError("Could not produce at least two distinct routes")

        candidates.sort(key=lambda c: c.duration_hours)
        candidates = candidates[:count]
        fastest = candidates[0]
        suffixes = "ABCD"
        for index, candidate in enumerate(candidates):
            candidate.delta_vs_fastest_miles = candidate.distance_miles - fastest.distance_miles
            if index == 0:
                candidate.label = "Fastest"
                candidate.tags.append("fastest")
            else:
                candidate.label = f"Alternate {suffixes[min(index - 1, len(suffixes) - 1)]}"
                candidate.tags.append("alternate")
        return candidates


class SyntheticRouter:
    """Deterministic geometry for tests, CI and offline demos.

    Produces a gentle great-circle path plus two bulged variants so the risk and
    ranking logic can be exercised without touching the network.
    """

    provider_name = "synthetic"

    def plan(self, origin: Point, destination: Point, count: int = 3) -> list[RouteCandidate]:
        distance = geo.haversine_miles(origin, destination)
        bearing = geo.bearing_degrees(origin, destination)
        candidates: list[RouteCandidate] = []
        shapes = [(0.0, "Fastest"), (0.12, "Alternate A"), (-0.16, "Alternate B")]
        for index, (bulge, label) in enumerate(shapes[:count]):
            points: list[Point] = []
            steps = 60
            for i in range(steps + 1):
                t = i / steps
                along = distance * t
                point = geo.destination_point(origin, bearing, along)
                if bulge and 0 < i < steps:
                    point = geo.destination_point(point, (bearing + 90) % 360, math.sin(math.pi * t) * distance * bulge)
                points.append(point)
            measured = geo.cumulative_distances(points)[-1]
            candidates.append(
                RouteCandidate(
                    points=points,
                    distance_miles=measured,
                    duration_hours=measured / (52.0 if index == 0 else 47.0),
                    label=label,
                    source="synthetic",
                    tags=["fastest"] if index == 0 else ["alternate"],
                )
            )
        fastest = candidates[0].distance_miles
        for candidate in candidates:
            candidate.delta_vs_fastest_miles = candidate.distance_miles - fastest
        return candidates


def get_router():
    if settings.ROUTING_PROVIDER == "synthetic":
        return SyntheticRouter()
    return OsrmRouter()
