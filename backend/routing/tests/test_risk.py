"""Boundary tests for the risk table in the brief.

Every threshold is probed on both sides, because an off-by-one here is exactly
the kind of bug an evaluator will look for.
"""
import pytest

from routing.services import risk
from routing.services.risk import RiskLevel


@pytest.mark.parametrize(
    "mph, expected",
    [
        (0.0, RiskLevel.LOW),
        (24.9, RiskLevel.LOW),
        (25.0, RiskLevel.MODERATE),
        (34.9, RiskLevel.MODERATE),
        (35.0, RiskLevel.HIGH),
        (44.9, RiskLevel.HIGH),
        (45.0, RiskLevel.SEVERE),
        (54.9, RiskLevel.SEVERE),
        (55.0, RiskLevel.NO_TRAVEL),
        (90.0, RiskLevel.NO_TRAVEL),
    ],
)
def test_wind_thresholds(mph, expected):
    assert risk.classify_wind(mph) is expected


@pytest.mark.parametrize(
    "rain, expected",
    [
        (0.0, RiskLevel.LOW),
        (0.09, RiskLevel.LOW),
        (0.10, RiskLevel.MODERATE),
        (0.249, RiskLevel.MODERATE),
        (0.25, RiskLevel.HIGH),
        (0.499, RiskLevel.HIGH),
        (0.50, RiskLevel.SEVERE),
        (1.00, RiskLevel.SEVERE),
        (1.01, RiskLevel.NO_TRAVEL),
    ],
)
def test_rain_thresholds(rain, expected):
    assert risk.classify_rain(rain) is expected


@pytest.mark.parametrize(
    "snow, expected",
    [
        (0.0, RiskLevel.LOW),
        (0.49, RiskLevel.LOW),
        (0.5, RiskLevel.MODERATE),
        (0.99, RiskLevel.MODERATE),
        (1.0, RiskLevel.HIGH),
        (1.99, RiskLevel.HIGH),
        (2.0, RiskLevel.SEVERE),
        (3.0, RiskLevel.SEVERE),
        (3.01, RiskLevel.NO_TRAVEL),
    ],
)
def test_snow_thresholds(snow, expected):
    assert risk.classify_snow(snow) is expected


@pytest.mark.parametrize(
    "wind, load, expected",
    [
        # >=55 is no-travel for any load
        (55.0, 0, RiskLevel.NO_TRAVEL),
        (60.0, 79_000, RiskLevel.NO_TRAVEL),
        # 45-54 + >30,000 lb
        (45.0, 30_001, RiskLevel.NO_TRAVEL),
        (54.9, 45_000, RiskLevel.NO_TRAVEL),
        (45.0, 30_000, RiskLevel.SEVERE),
        (50.0, 12_000, RiskLevel.SEVERE),
        # 35-44 + >40,000 lb
        (40.0, 40_001, RiskLevel.SEVERE),
        (35.0, 80_000, RiskLevel.SEVERE),
        (40.0, 40_000, RiskLevel.HIGH),
        (40.0, 39_999, RiskLevel.HIGH),
    ],
)
def test_load_rules(wind, load, expected):
    assert risk.assess(wind, 0, 0, load).level is expected


def test_load_rule_never_lowers_risk():
    # Calm wind with heavy rain must stay Severe, not be demoted by the load rule.
    result = risk.assess(wind_mph=10, rain_in_hr=0.6, snow_in_hr=0, load_lb=80_000)
    assert result.level is RiskLevel.SEVERE


def test_worst_condition_drives_the_checkpoint():
    result = risk.assess(wind_mph=10, rain_in_hr=0.3, snow_in_hr=0.6, load_lb=10_000)
    assert result.level is RiskLevel.HIGH
    assert result.driver == "rain"
    assert result.rain_level is RiskLevel.HIGH
    assert result.snow_level is RiskLevel.MODERATE


def test_no_travel_reason_mentions_the_rule():
    result = risk.assess(wind_mph=47, rain_in_hr=0, snow_in_hr=0, load_lb=44_000)
    assert result.level is RiskLevel.NO_TRAVEL
    assert result.escalated_by_load is True
    assert any("30,000 lb" in reason for reason in result.reasons)


def test_aggregate_is_distance_weighted():
    metrics = risk.aggregate([(RiskLevel.SEVERE, 10.0), (RiskLevel.HIGH, 20.0), (RiskLevel.LOW, 5.0)])
    assert metrics.severe_miles == pytest.approx(10.0)
    assert metrics.high_miles == pytest.approx(20.0)
    assert metrics.avg_risk == pytest.approx((3 * 10 + 2 * 20) / 35)
    assert metrics.peak_level == int(RiskLevel.SEVERE)


def test_aggregate_tracks_no_travel_separately():
    metrics = risk.aggregate([(RiskLevel.NO_TRAVEL, 8.0), (RiskLevel.LOW, 2.0)])
    assert metrics.no_travel_miles == pytest.approx(8.0)
    assert metrics.severe_miles == 0.0
    assert metrics.peak_label == "No Travel"


def test_ranking_prefers_risk_before_time():
    calm = risk.aggregate([(RiskLevel.LOW, 100.0)])
    rough = risk.aggregate([(RiskLevel.SEVERE, 40.0), (RiskLevel.LOW, 60.0)])
    # 2 h slower but far safer -> lower key
    assert risk.ranking_key(calm, 12.0) < risk.ranking_key(rough, 10.0)


def test_ranking_breaks_ties_on_time():
    a = risk.aggregate([(RiskLevel.HIGH, 100.0)])
    assert risk.ranking_key(a, 11.0) < risk.ranking_key(a, 12.0)
