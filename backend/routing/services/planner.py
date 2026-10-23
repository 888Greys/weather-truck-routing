"""Plan assembly: routes -> checkpoints -> weather -> risk -> recommendation.

The whole pipeline is deterministic given its inputs apart from the upstream
numbers, which makes it straightforward to test with the synthetic providers.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from django.conf import settings

from . import geo, risk
from .geo import Point
from .routing import RouteCandidate, get_router
from .weather import Forecast, get_weather_provider

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PlanInput:
    origin: Point
    destination: Point
    depart_at: datetime
    weight_lb: float
    spacing_miles: float = 25.0
    horizon_hours: int = 48
    origin_label: str = ""
    destination_label: str = ""
    scenario: str = "live"


@dataclass(slots=True)
class _RouteState:
    candidate: RouteCandidate
    route_id: str
    checkpoints: list[dict]
    metrics: risk.RouteMetrics
    eta_hours: list[float]


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _route_id(index: int) -> str:
    return f"route-{index + 1}"


def _checkpoint_payload(
    miles: float,
    point: Point,
    eta_epoch: float,
    sample,
    assessment: risk.RiskAssessment,
    segment_miles: float,
) -> dict:
    return {
        "miles": round(miles, 1),
        "lat": round(point.lat, 5),
        "lon": round(point.lon, 5),
        "eta": _iso(eta_epoch),
        "segment_miles": round(segment_miles, 1),
        "wind_mph": round(sample.wind_mph, 1),
        "rain_in_hr": round(sample.rain_in_hr, 3),
        "snow_in_hr": round(sample.snow_in_hr, 3),
        "temp_c": round(sample.temp_c, 1),
        "weather_code": int(sample.code or 0),
        "level": int(assessment.level),
        "level_label": assessment.label,
        "driver": assessment.driver,
        "reasons": list(assessment.reasons),
        "load_escalated": assessment.escalated_by_load,
        "weather_available": bool(sample.available),
    }


def _rationale(best: _RouteState, others: list[_RouteState]) -> list[str]:
    lines: list[str] = []
    m = best.metrics
    if m.no_travel_miles > 0:
        lines.append(
            f"{best.candidate.label} still contains {m.no_travel_miles:.0f} mi of no-travel weather - consider delaying departure."
        )
    elif m.severe_miles == 0:
        lines.append(f"{best.candidate.label} never reaches Severe, so it wins the first criterion outright.")
    else:
        lines.append(
            f"{best.candidate.label} has the fewest Severe miles ({m.severe_miles:.0f} mi) of the options."
        )

    for other in others:
        om = other.metrics
        if om.severe_miles > m.severe_miles:
            lines.append(
                f"{other.candidate.label} carries {om.severe_miles:.0f} Severe mi vs {m.severe_miles:.0f} mi here."
            )
        elif om.high_miles > m.high_miles:
            lines.append(
                f"{other.candidate.label} has {om.high_miles:.0f} High mi vs {m.high_miles:.0f} mi here, which loses the second criterion."
            )

    faster = [o for o in others if o.candidate.duration_hours + 0.05 < best.candidate.duration_hours]
    if faster:
        quickest = min(faster, key=lambda o: o.candidate.duration_hours)
        delta = best.candidate.duration_hours - quickest.candidate.duration_hours
        lines.append(
            f"{quickest.candidate.label} is {delta * 60:.0f} min quicker but ranks lower on weather risk, and risk outranks time."
        )
    else:
        lines.append(f"It is also the quickest option at {best.candidate.duration_hours:.1f} h.")
    return lines[:4]


def _summarise(state: _RouteState) -> str:
    m = state.metrics
    bits = [f"{state.candidate.distance_miles:.0f} mi", f"{state.candidate.duration_hours:.1f} h"]
    if m.no_travel_miles:
        bits.append(f"{m.no_travel_miles:.0f} mi no-travel")
    if m.severe_miles:
        bits.append(f"{m.severe_miles:.0f} mi severe")
    if m.high_miles:
        bits.append(f"{m.high_miles:.0f} mi high")
    if not (m.severe_miles or m.high_miles or m.no_travel_miles):
        bits.append("no severe or high road")
    return " - ".join(bits)


def build_plan(payload: PlanInput) -> dict:
    depart = payload.depart_at.astimezone(timezone.utc)
    horizon = min(payload.horizon_hours, settings.FORECAST_HORIZON_HOURS)
    degraded = {"routing": False, "weather": False}

    router = get_router()
    try:
        candidates = router.plan(payload.origin, payload.destination, count=3)
    except Exception as exc:  # noqa: BLE001 - fall back so the demo still works
        logger.warning("Routing failed (%s); using synthetic geometry", exc)
        from .routing import SyntheticRouter

        candidates = SyntheticRouter().plan(payload.origin, payload.destination, count=3)
        degraded["routing"] = True

    # 1. Sample checkpoints and heat-map cells up front, so a single weather
    #    fetch can cover every coordinate either of them needs.
    sampled: list[tuple[RouteCandidate, list[tuple[float, Point]], list[tuple[float, Point]], float]] = []
    for candidate in candidates:
        total = geo.cumulative_distances(candidate.points)[-1]
        samples = geo.sample_along_route(candidate.points, payload.spacing_miles, settings.MAX_ROUTE_CHECKPOINTS)
        cell_count = max(8, int(total // settings.HEATMAP_SPACING_MILES) + 2)
        cells = geo.sample_along_route(candidate.points, settings.HEATMAP_SPACING_MILES, cell_count)
        sampled.append((candidate, samples, cells, total))

    # 2. One weather request set for every unique point on every route.
    unique_points = geo.dedupe_points(
        [p for _, samples, cells, _ in sampled for _, p in (*samples, *cells)]
    )
    index_of = {(round(p.lat, 3), round(p.lon, 3)): i for i, p in enumerate(unique_points)}
    longest = max((c.duration_hours for c in candidates), default=1.0)
    end = depart + timedelta(hours=horizon + max(1.0, longest) + 2)

    if payload.scenario == "stress":
        # A clearly-labelled simulated system, so the severe / no-travel branches
        # of the rules can be demonstrated even on a calm-weather day.
        from .weather import SyntheticWeather

        forecasts = SyntheticWeather().fetch_many(unique_points, depart, end)
    else:
        weather = get_weather_provider()
        try:
            forecasts = weather.fetch_many(unique_points, depart, end)
        except Exception as exc:  # noqa: BLE001 - degrade to synthetic weather
            logger.warning("Weather provider failed (%s); using synthetic weather", exc)
            from .weather import SyntheticWeather

            forecasts = SyntheticWeather().fetch_many(unique_points, depart, end)
            degraded["weather"] = True

    # 3. Classify every checkpoint.
    states: list[_RouteState] = []
    for index, (candidate, samples, _cells, total) in enumerate(sampled):
        points: list[dict] = []
        pairs: list[tuple[risk.RiskLevel, float]] = []
        etas: list[float] = []
        previous_miles = 0.0
        for miles, point in samples:
            fraction = miles / total if total else 0.0
            eta_hours = candidate.duration_hours * fraction
            eta_epoch = depart.timestamp() + eta_hours * 3600.0
            forecast = forecasts[index_of[(round(point.lat, 3), round(point.lon, 3))]]
            sample = forecast.sample(eta_epoch)
            assessment = risk.assess(sample.wind_mph, sample.rain_in_hr, sample.snow_in_hr, payload.weight_lb)
            segment = max(0.0, miles - previous_miles)
            previous_miles = miles
            pairs.append((assessment.level, segment))
            etas.append(eta_hours)
            points.append(_checkpoint_payload(miles, point, eta_epoch, sample, assessment, segment))

        states.append(
            _RouteState(
                candidate=candidate,
                route_id=_route_id(index),
                checkpoints=points,
                metrics=risk.aggregate(pairs),
                eta_hours=etas,
            )
        )

    # 4. Rank with the brief's preference order.
    states.sort(key=lambda s: risk.ranking_key(s.metrics, s.candidate.duration_hours))
    for rank_index, state in enumerate(states):
        state.route_id = _route_id(rank_index)

    best = states[0]
    others = states[1:]

    # 5. Corridor heat map: every cell at every hour offset from departure.
    heatmap_routes: dict[str, dict] = {}
    hours = list(range(horizon + 1))
    cells_by_candidate = {id(candidate): (cells, total) for candidate, _s, cells, total in sampled}
    for state in states:
        cell_samples, total = cells_by_candidate[id(state.candidate)]
        cells = []
        for miles, point in cell_samples:
            fraction = miles / total if total else 0.0
            eta_epoch = depart.timestamp() + state.candidate.duration_hours * fraction * 3600.0
            forecast = forecasts[index_of[(round(point.lat, 3), round(point.lon, 3))]]
            levels = []
            for offset in hours:
                sample = forecast.sample(eta_epoch + offset * 3600.0)
                levels.append(int(risk.assess(sample.wind_mph, sample.rain_in_hr, sample.snow_in_hr, payload.weight_lb).level))
            cells.append(
                {
                    "lat": round(point.lat, 5),
                    "lon": round(point.lon, 5),
                    "miles": round(miles, 1),
                    "levels": levels,
                }
            )
        heatmap_routes[state.route_id] = {"cells": cells}

    routes_payload = []
    for rank_index, state in enumerate(states):
        candidate = state.candidate
        routes_payload.append(
            {
                "id": state.route_id,
                "rank": rank_index + 1,
                "label": candidate.label or f"Route {rank_index + 1}",
                "is_recommended": rank_index == 0,
                "source": candidate.source,
                "distance_miles": round(cells_by_candidate[id(candidate)][1], 1),
                "delta_vs_fastest_miles": round(candidate.delta_vs_fastest_miles, 1),
                "duration_hours": round(candidate.duration_hours, 2),
                "geometry": [p.as_list() for p in geo.simplify(candidate.points, 900)],
                "checkpoints": state.checkpoints,
                "metrics": state.metrics.as_dict(),
                "summary": _summarise(state),
            }
        )

    return {
        "generated_at": _iso(datetime.now(tz=timezone.utc).timestamp()),
        "request": {
            "origin": {
                "lat": round(payload.origin.lat, 5),
                "lon": round(payload.origin.lon, 5),
                "label": payload.origin_label,
            },
            "destination": {
                "lat": round(payload.destination.lat, 5),
                "lon": round(payload.destination.lon, 5),
                "label": payload.destination_label,
            },
            "depart_at": _iso(depart.timestamp()),
            "weight_lb": payload.weight_lb,
            "sample_interval_miles": payload.spacing_miles,
            "horizon_hours": horizon,
            "scenario": payload.scenario,
        },
        "routes": routes_payload,
        "recommendation": {
            "route_id": best.route_id,
            "label": best.candidate.label,
            "rationale": _rationale(best, others),
            "ranking": [
                {
                    "route_id": s.route_id,
                    "label": s.candidate.label,
                    "rank": i + 1,
                    "why": "recommended" if i == 0 else f"ranked {i + 1} on risk then time",
                }
                for i, s in enumerate(states)
            ],
        },
        "heatmap": {
            "horizon_hours": horizon,
            "spacing_miles": settings.HEATMAP_SPACING_MILES,
            "hours": [(depart + timedelta(hours=h)).isoformat().replace("+00:00", "Z") for h in hours],
            "routes": heatmap_routes,
        },
        "legend": risk.risk_color_legend(),
        "meta": {
            "routing_provider": "synthetic" if degraded["routing"] else settings.ROUTING_PROVIDER,
            "weather_provider": (
                "simulated-storm"
                if payload.scenario == "stress"
                else ("synthetic" if degraded["weather"] else settings.WEATHER_PROVIDER)
            ),
            "scenario": payload.scenario,
            "degraded": degraded,
            "checkpoints_per_route": [len(r["checkpoints"]) for r in routes_payload],
        },
    }
