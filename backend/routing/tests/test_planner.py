from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from routing.services import geo, risk
from routing.services.geo import Point
from routing.services.planner import PlanInput, build_plan

NAIROBI = Point(-1.2921, 36.8219)
MOMBASA = Point(-4.0435, 39.6682)


def make_input(**overrides) -> PlanInput:
    base = dict(
        origin=NAIROBI,
        destination=MOMBASA,
        depart_at=timezone.now() + timedelta(hours=3),
        weight_lb=42_000,
        spacing_miles=25.0,
        horizon_hours=48,
    )
    base.update(overrides)
    return PlanInput(**base)


@pytest.fixture
def plan():
    with override_settings(ROUTING_PROVIDER="synthetic", WEATHER_PROVIDER="synthetic"):
        return build_plan(make_input())


def test_returns_three_distinct_routes(plan):
    routes = plan["routes"]
    assert len(routes) == 3
    ids = {r["id"] for r in routes}
    assert len(ids) == 3
    distances = [r["distance_miles"] for r in routes]
    assert len(set(round(d) for d in distances)) > 1


def test_exactly_one_recommendation_and_consistent_ranks(plan):
    recommended = [r for r in plan["routes"] if r["is_recommended"]]
    assert len(recommended) == 1
    assert plan["recommendation"]["route_id"] == recommended[0]["id"]
    assert [r["rank"] for r in plan["routes"]] == [1, 2, 3]


def test_routes_are_ordered_by_the_briefs_criteria(plan):
    keys = [
        (
            r["metrics"]["no_travel_miles"],
            r["metrics"]["severe_miles"],
            r["metrics"]["high_miles"],
            r["metrics"]["avg_risk"],
            r["duration_hours"],
        )
        for r in plan["routes"]
    ]
    assert keys == sorted(keys)


def test_checkpoints_follow_the_requested_spacing(plan):
    route = plan["routes"][0]
    distances = [c["miles"] for c in route["checkpoints"]]
    assert distances[0] == 0.0
    assert distances[-1] == pytest.approx(route["distance_miles"], abs=0.2)
    gaps = [b - a for a, b in zip(distances, distances[1:])]
    assert max(gaps) <= 25.0 + 0.2


def test_checkpoint_etas_are_monotonic_and_start_at_departure(plan):
    route = plan["routes"][0]
    etas = [c["eta"] for c in route["checkpoints"]]
    assert etas == sorted(etas)
    assert etas[0] == plan["request"]["depart_at"]


def test_checkpoint_payload_has_everything_the_ui_needs(plan):
    checkpoint = plan["routes"][0]["checkpoints"][1]
    for field in (
        "miles", "lat", "lon", "eta", "segment_miles", "wind_mph", "rain_in_hr",
        "snow_in_hr", "temp_c", "level", "level_label", "driver", "reasons",
    ):
        assert field in checkpoint
    assert 0 <= checkpoint["level"] <= 4


def test_segment_miles_sum_to_route_distance(plan):
    route = plan["routes"][0]
    total = sum(c["segment_miles"] for c in route["checkpoints"])
    assert total == pytest.approx(route["distance_miles"], abs=0.5)


def test_no_duplicate_checkpoint_mileage(plan):
    """A route just over a multiple of the spacing must not repeat its last stop."""
    for route in plan["routes"]:
        miles = [c["miles"] for c in route["checkpoints"]]
        assert len(miles) == len(set(miles)), "duplicate checkpoints in " + route["id"]


def test_risk_miles_add_up_to_the_route(plan):
    for route in plan["routes"]:
        metrics = route["metrics"]
        covered = (
            metrics["severe_miles"]
            + metrics["high_miles"]
            + metrics["moderate_miles"]
            + metrics["low_miles"]
            + metrics["no_travel_miles"]
        )
        assert covered == pytest.approx(route["distance_miles"], abs=0.5)


def test_heatmap_covers_every_hour_and_route(plan):
    heatmap = plan["heatmap"]
    assert heatmap["horizon_hours"] == 48
    assert len(heatmap["hours"]) == 49
    for route in plan["routes"]:
        cells = heatmap["routes"][route["id"]]["cells"]
        assert len(cells) >= 8
        for cell in cells:
            assert len(cell["levels"]) == 49
            assert all(0 <= level <= 4 for level in cell["levels"])


def test_heatmap_hour_zero_matches_checkpoint_risk(plan):
    """Slider at offset 0 must agree with the checkpoint risk shown on the map."""
    route = plan["routes"][0]
    cells = plan["heatmap"]["routes"][route["id"]]["cells"]
    checkpoint_miles = {round(c["miles"], 1): c["level"] for c in route["checkpoints"]}
    matched = 0
    for cell in cells:
        key = round(cell["miles"], 1)
        if key in checkpoint_miles:
            assert cell["levels"][0] == checkpoint_miles[key]
            matched += 1
    assert matched > 0


def test_heavier_load_is_never_safer(plan):
    with override_settings(ROUTING_PROVIDER="synthetic", WEATHER_PROVIDER="synthetic"):
        heavy = build_plan(make_input(weight_lb=79_000))
    light = plan
    for heavier, lighter in zip(heavy["routes"], light["routes"]):
        assert heavier["metrics"]["avg_risk"] >= lighter["metrics"]["avg_risk"] - 1e-9


def test_spacing_option_changes_checkpoint_count():
    with override_settings(ROUTING_PROVIDER="synthetic", WEATHER_PROVIDER="synthetic"):
        coarse = build_plan(make_input(spacing_miles=50.0))
        fine = build_plan(make_input(spacing_miles=10.0))
    fine_total = sum(len(r["checkpoints"]) for r in fine["routes"])
    coarse_total = sum(len(r["checkpoints"]) for r in coarse["routes"])
    assert fine_total > coarse_total
    for route in fine["routes"]:
        gaps = [b["miles"] - a["miles"] for a, b in zip(route["checkpoints"], route["checkpoints"][1:])]
        assert max(gaps) <= 10.0 + 0.2


def test_plan_is_deterministic_for_identical_inputs():
    payload = make_input()
    with override_settings(ROUTING_PROVIDER="synthetic", WEATHER_PROVIDER="synthetic"):
        first = build_plan(payload)
        second = build_plan(payload)
    assert [r["metrics"] for r in first["routes"]] == [r["metrics"] for r in second["routes"]]
    assert first["heatmap"]["routes"] == second["heatmap"]["routes"]


def test_rationale_is_populated(plan):
    rationale = plan["recommendation"]["rationale"]
    assert 1 <= len(rationale) <= 4
    assert all(isinstance(line, str) and line for line in rationale)
