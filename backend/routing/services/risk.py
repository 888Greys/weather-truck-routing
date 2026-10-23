"""Weather + load risk model.

The thresholds are transcribed verbatim from the assessment brief:

    Wind   Low <25 | Moderate 25-34 | High 35-44 | Severe 45-54 | No Travel >=55  (mph)
    Rain   Low <0.10 | Moderate 0.10-0.25 | High 0.25-0.50 | Severe 0.50-1.00 | No Travel >1.00 (in/hr)
    Snow   Low <0.5 | Moderate 0.5-1.0 | High 1.0-2.0 | Severe 2.0-3.0 | No Travel >3.0 (in/hr)

    Load:  >=55 mph -> No Travel for any load
           45-54 mph + >30,000 lb -> No Travel
           35-44 mph + >40,000 lb -> Severe

Boundary policy: the table's upper bounds are inclusive where written as a
closed range (wind 25-34, rain 0.50-1.00) and exclusive where written as an
open bound (rain >1.00, snow >3.0). Buckets are therefore half-open on the
lower edge, which makes every point on the number line classify exactly once.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable, Sequence


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4


LEVEL_LABELS: dict[RiskLevel, str] = {
    RiskLevel.LOW: "Low",
    RiskLevel.MODERATE: "Moderate",
    RiskLevel.HIGH: "High",
    RiskLevel.SEVERE: "Severe",
    RiskLevel.NO_TRAVEL: "No Travel",
}

#: Load rule constants (pounds).
LOAD_NO_TRAVEL_ABOVE = 30_000
LOAD_SEVERE_ABOVE = 40_000


def classify_wind(mph: float) -> RiskLevel:
    if mph >= 55:
        return RiskLevel.NO_TRAVEL
    if mph >= 45:
        return RiskLevel.SEVERE
    if mph >= 35:
        return RiskLevel.HIGH
    if mph >= 25:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def classify_rain(inches_per_hour: float) -> RiskLevel:
    if inches_per_hour > 1.00:
        return RiskLevel.NO_TRAVEL
    if inches_per_hour >= 0.50:
        return RiskLevel.SEVERE
    if inches_per_hour >= 0.25:
        return RiskLevel.HIGH
    if inches_per_hour >= 0.10:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def classify_snow(inches_per_hour: float) -> RiskLevel:
    if inches_per_hour > 3.0:
        return RiskLevel.NO_TRAVEL
    if inches_per_hour >= 2.0:
        return RiskLevel.SEVERE
    if inches_per_hour >= 1.0:
        return RiskLevel.HIGH
    if inches_per_hour >= 0.5:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    level: RiskLevel
    label: str
    driver: str
    wind_level: RiskLevel
    rain_level: RiskLevel
    snow_level: RiskLevel
    reasons: tuple[str, ...]
    escalated_by_load: bool


def assess(
    wind_mph: float,
    rain_in_hr: float,
    snow_in_hr: float,
    load_lb: float = 0.0,
) -> RiskAssessment:
    """Classify one checkpoint, applying the load escalation rules last."""
    wind_lvl = classify_wind(wind_mph)
    rain_lvl = classify_rain(rain_in_hr)
    snow_lvl = classify_snow(snow_in_hr)

    candidates = (("wind", wind_lvl), ("rain", rain_lvl), ("snow", snow_lvl))
    driver, level = max(candidates, key=lambda item: item[1])

    reasons: list[str] = []
    escalated = False

    # Load rules run on the raw wind value, not the wind bucket, so the band
    # edges stay exactly where the brief puts them.
    if wind_mph >= 55:
        reasons.append(f"Wind {wind_mph:.0f} mph >= 55 mph: no travel for any load")
    elif 45 <= wind_mph < 55 and load_lb > LOAD_NO_TRAVEL_ABOVE:
        reasons.append(
            f"Wind {wind_mph:.0f} mph with {load_lb:,.0f} lb load (>30,000 lb): no travel"
        )
        level, driver = RiskLevel.NO_TRAVEL, "load"
        escalated = True
    elif 35 <= wind_mph < 45 and load_lb > LOAD_SEVERE_ABOVE:
        if level < RiskLevel.SEVERE:
            escalated = True
        reasons.append(
            f"Wind {wind_mph:.0f} mph with {load_lb:,.0f} lb load (>40,000 lb): severe"
        )
        if level < RiskLevel.SEVERE:
            level, driver = RiskLevel.SEVERE, "load"

    if rain_in_hr > 1.00:
        reasons.append(f"Rain {rain_in_hr:.2f} in/hr > 1.00 in/hr: no travel")
    elif snow_in_hr > 3.0:
        reasons.append(f"Snow {snow_in_hr:.2f} in/hr > 3.0 in/hr: no travel")

    if not reasons:
        reasons.append(f"{driver.capitalize()} conditions at {LEVEL_LABELS[level]}")

    return RiskAssessment(
        level=level,
        label=LEVEL_LABELS[level],
        driver=driver,
        wind_level=wind_lvl,
        rain_level=rain_lvl,
        snow_level=snow_lvl,
        reasons=tuple(reasons),
        escalated_by_load=escalated,
    )


@dataclass(frozen=True, slots=True)
class RouteMetrics:
    severe_miles: float
    high_miles: float
    moderate_miles: float
    low_miles: float
    no_travel_miles: float
    avg_risk: float
    peak_level: int
    worst_checkpoint_miles: float | None

    @property
    def peak_label(self) -> str:
        return LEVEL_LABELS[RiskLevel(self.peak_level)]

    def as_dict(self) -> dict:
        return {
            "severe_miles": round(self.severe_miles, 1),
            "high_miles": round(self.high_miles, 1),
            "moderate_miles": round(self.moderate_miles, 1),
            "low_miles": round(self.low_miles, 1),
            "no_travel_miles": round(self.no_travel_miles, 1),
            "avg_risk": round(self.avg_risk, 3),
            "peak_level": self.peak_level,
            "peak_label": self.peak_label,
            "worst_checkpoint_miles": (
                round(self.worst_checkpoint_miles, 1) if self.worst_checkpoint_miles is not None else None
            ),
        }


def aggregate(checkpoints: Sequence[tuple[RiskLevel, float]]) -> RouteMetrics:
    """Roll checkpoint levels up into the four ranking signals.

    Each checkpoint represents the stretch of road from the previous checkpoint
    up to itself, so risk miles add up to the route distance.
    """
    miles = {lvl: 0.0 for lvl in RiskLevel}
    weighted = 0.0
    total = 0.0
    peak = RiskLevel.LOW
    worst_at: float | None = None
    cursor = 0.0

    for level, span in checkpoints:
        span = max(0.0, float(span))
        miles[level] += span
        weighted += level * span
        total += span
        cursor += span
        if level > peak:
            peak = level
            worst_at = cursor
        elif level == peak and worst_at is None:
            worst_at = cursor

    avg = weighted / total if total else 0.0
    return RouteMetrics(
        severe_miles=miles[RiskLevel.SEVERE],
        high_miles=miles[RiskLevel.HIGH],
        moderate_miles=miles[RiskLevel.MODERATE],
        low_miles=miles[RiskLevel.LOW],
        no_travel_miles=miles[RiskLevel.NO_TRAVEL],
        avg_risk=avg,
        peak_level=int(peak),
        worst_checkpoint_miles=worst_at,
    )


def ranking_key(metrics: RouteMetrics, duration_hours: float) -> tuple[float, ...]:
    """Lexicographic order matching the brief's preference list.

    No-travel miles lead because a route with a stop-the-truck segment is worse
    than any amount of merely severe road, then the brief's four criteria.
    """
    return (
        metrics.no_travel_miles,
        metrics.severe_miles,
        metrics.high_miles,
        round(metrics.avg_risk, 6),
        round(duration_hours, 6),
    )


def risk_color_legend() -> list[dict]:
    return [
        {"level": int(RiskLevel.LOW), "label": "Low", "color": "#2f9e5f"},
        {"level": int(RiskLevel.MODERATE), "label": "Moderate", "color": "#d8a72a"},
        {"level": int(RiskLevel.HIGH), "label": "High", "color": "#e07b26"},
        {"level": int(RiskLevel.SEVERE), "label": "Severe", "color": "#e05252"},
        {"level": int(RiskLevel.NO_TRAVEL), "label": "No Travel", "color": "#8c2f43"},
    ]
