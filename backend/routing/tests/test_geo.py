import math

import pytest

from routing.services import geo
from routing.services.geo import Point


def test_haversine_matches_known_distance():
    nairobi = Point(-1.2921, 36.8219)
    mombasa = Point(-4.0435, 39.6682)
    # Great-circle distance is ~273 mi; the road is ~300 mi.
    assert 265 < geo.haversine_miles(nairobi, mombasa) < 285


def test_haversine_is_symmetric_and_zero_at_identity():
    a, b = Point(0, 0), Point(10, 10)
    assert geo.haversine_miles(a, b) == pytest.approx(geo.haversine_miles(b, a))
    assert geo.haversine_miles(a, a) == pytest.approx(0.0)


def test_cumulative_distances_are_monotonic():
    points = [Point(0, 0), Point(0, 1), Point(0, 2)]
    cumulative = geo.cumulative_distances(points)
    assert cumulative[0] == 0
    assert cumulative == sorted(cumulative)


def test_point_at_distance_clamps_to_ends():
    points = [Point(0, 0), Point(0, 1)]
    cumulative = geo.cumulative_distances(points)
    assert geo.point_at_distance(points, cumulative, -5) == points[0]
    assert geo.point_at_distance(points, cumulative, 10_000) == points[-1]


def test_points_are_evenly_spaced_and_end_exactly_on_the_destination():
    points = [Point(0, 0), Point(0, 1), Point(0, 2)]
    samples = geo.sample_along_route(points, 25.0)
    total = geo.cumulative_distances(points)[-1]
    gaps = [b[0] - a[0] for a, b in zip(samples, samples[1:])]
    assert all(gap <= 25.0 + 1e-6 for gap in gaps)
    assert samples[-1][0] == pytest.approx(total)
    assert samples[0][0] == 0


def test_sampling_respects_max_samples():
    points = [Point(0, i * 0.05) for i in range(400)]
    samples = geo.sample_along_route(points, 1.0, max_samples=50)
    assert len(samples) <= 50


def test_offset_waypoint_sits_beside_the_route():
    points = [Point(0, 0), Point(0, 2)]
    cumulative = geo.cumulative_distances(points)
    via = geo.offset_waypoint(points, cumulative, 0.5, 20.0)
    nearest = min(geo.haversine_miles(via, p) for p in points)
    assert nearest > 5


def test_simplify_keeps_the_endpoints():
    points = [Point(0, i * 0.01) for i in range(1000)]
    simplified = geo.simplify(points, 100)
    assert len(simplified) == 100
    assert simplified[0] == points[0]
    assert simplified[-1] == points[-1]


def test_destination_point_round_trip():
    start = Point(-1.29, 36.82)
    bearing = geo.bearing_degrees(start, Point(-4.04, 39.67))
    moved = geo.destination_point(start, bearing, 100.0)
    assert geo.haversine_miles(start, moved) == pytest.approx(100.0, abs=0.5)
