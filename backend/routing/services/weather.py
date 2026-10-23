"""Hourly weather for arbitrary points along a corridor.

Open-Meteo is used because it needs no API key, returns hourly values for up to
16 days, and accepts many coordinates per request - which is what makes a
48-hour corridor heat map affordable inside a hobby-tier quota.
"""
from __future__ import annotations

import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone

from django.conf import settings

from .cache import WEATHER_TTL, memo
from .geo import Point
from .http import UpstreamError, get_json

logger = logging.getLogger(__name__)

BATCH_SIZE = 20


@dataclass(frozen=True, slots=True)
class WeatherSample:
    wind_mph: float
    rain_in_hr: float
    snow_in_hr: float
    temp_c: float
    code: int
    available: bool = True


EMPTY_SAMPLE = WeatherSample(0.0, 0.0, 0.0, 15.0, 0, available=False)


@dataclass(slots=True)
class Forecast:
    start_epoch: int
    wind_mph: list[float]
    rain_in_hr: list[float]
    snow_in_hr: list[float]
    temp_c: list[float]
    code: list[int]

    @property
    def hours(self) -> int:
        return len(self.wind_mph)

    def sample(self, epoch: float) -> WeatherSample:
        if not self.wind_mph:
            return EMPTY_SAMPLE
        index = int(round((epoch - self.start_epoch) / 3600.0))
        clamped = max(0, min(index, self.hours - 1))
        return WeatherSample(
            wind_mph=self.wind_mph[clamped],
            rain_in_hr=self.rain_in_hr[clamped],
            snow_in_hr=self.snow_in_hr[clamped],
            temp_c=self.temp_c[clamped],
            code=self.code[clamped],
            available=index == clamped,
        )


def _parse_utc(value: str) -> int:
    return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp())


class OpenMeteoWeather:
    provider_name = "open-meteo"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.OPEN_METEO_BASE_URL).rstrip("/")

    def _fetch_chunk(self, points: list[Point], start: datetime, end: datetime) -> list[Forecast]:
        span_hours = max(1.0, (end - start).total_seconds() / 3600.0)
        forecast_days = max(1, min(16, math.ceil(span_hours / 24) + 1))
        past_days = 1 if start.timestamp() < time.time() - 3600 else 0

        payload = get_json(
            f"{self.base_url}/v1/forecast",
            {
                "latitude": ",".join(f"{p.lat:.4f}" for p in points),
                "longitude": ",".join(f"{p.lon:.4f}" for p in points),
                "hourly": "wind_speed_10m,rain,snowfall,temperature_2m,weather_code",
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "timezone": "UTC",
                "forecast_days": forecast_days,
                "past_days": past_days,
                "cell_selection": "nearest",
            },
        )
        results = payload if isinstance(payload, list) else [payload]
        forecasts: list[Forecast] = []
        for item in results:
            hourly = item.get("hourly") or {}
            times = hourly.get("time") or []
            if not times:
                forecasts.append(Forecast(0, [], [], [], [], []))
                continue
            forecasts.append(
                Forecast(
                    start_epoch=_parse_utc(times[0]),
                    wind_mph=[float(v or 0) for v in hourly.get("wind_speed_10m", [])],
                    rain_in_hr=[float(v or 0) for v in hourly.get("rain", [])],
                    snow_in_hr=[float(v or 0) for v in hourly.get("snowfall", [])],
                    temp_c=[float(v or 0) for v in hourly.get("temperature_2m", [])],
                    code=[int(v or 0) for v in hourly.get("weather_code", [])],
                )
            )
        while len(forecasts) < len(points):
            forecasts.append(Forecast(0, [], [], [], [], []))
        return forecasts

    def fetch_many(self, points: list[Point], start: datetime, end: datetime) -> list[Forecast]:
        """Forecasts for every point, in the same order, batched and cached."""
        if not points:
            return []
        start = start.astimezone(timezone.utc)
        end = end.astimezone(timezone.utc)

        chunks = [points[i : i + BATCH_SIZE] for i in range(0, len(points), BATCH_SIZE)]

        def run(chunk: list[Point]) -> list[Forecast]:
            cache_key = {
                "points": [(round(p.lat, 2), round(p.lon, 2)) for p in chunk],
                "start": start.strftime("%Y-%m-%dT%H"),
                "end": end.strftime("%Y-%m-%dT%H"),
            }
            return memo(
                "weather",
                cache_key,
                WEATHER_TTL,
                lambda: self._fetch_chunk(chunk, start, end),
            )

        if len(chunks) == 1:
            return run(chunks[0])
        with ThreadPoolExecutor(max_workers=min(4, len(chunks))) as pool:
            results = list(pool.map(run, chunks))
        return [forecast for group in results for forecast in group]


class SyntheticWeather:
    """Smooth, deterministic weather field.

    Two travelling systems (one wind, one precipitation) move east across the
    map, so scrubbing the 48-hour slider visibly changes the corridor instead of
    flickering between random values.
    """

    provider_name = "synthetic"

    def __init__(self, intensity: float | None = None) -> None:
        self.intensity = intensity if intensity is not None else 1.0

    # Tuned so a storm scenario lands roughly 33% Low / 27% Moderate / 17% High /
    # 23% Severe / 3% No Travel at a 20 klb load, with the load rules visibly
    # shifting High into Severe and No Travel as weight climbs.
    WIND_BASE = 24.0
    WIND_AMPLITUDE = 10.0
    WIND_STORM_BOOST = 16.0
    RAIN_SCALE = 1.0

    def _field(self, point: Point, hours_ahead: float) -> WeatherSample:
        lat, lon = point.lat, point.lon
        drift = hours_ahead * 0.06
        wave = math.sin(1.9 * lat + 1.1 * (lon + drift)) + 0.6 * math.sin(4.3 * lat - 2.1 * (lon + drift) + 1.7)
        storm = math.sin(1.7 * (lat + 0.4) - 1.5 * (lon + drift * 0.8) + 2.2)
        core = max(0.0, storm) ** 2
        wind = max(0.0, self.WIND_BASE + self.WIND_AMPLITUDE * wave + self.WIND_STORM_BOOST * core) * self.intensity
        rain = core * self.RAIN_SCALE * self.intensity
        snow = 0.0
        if lat > 38.0:
            snow = core * 2.6 * ((lat - 38.0) / 8.0) * self.intensity
        temp = 18.0 - 0.9 * max(0.0, lat - 30.0) - 4.0 * core + 3.0 * math.sin(hours_ahead / 9.0)
        code = 61 if rain > 0.1 else (71 if snow > 0.2 else 3)
        return WeatherSample(
            wind_mph=round(wind, 1),
            rain_in_hr=round(rain, 3),
            snow_in_hr=round(snow, 3),
            temp_c=round(temp, 1),
            code=code,
        )

    def fetch_many(self, points: list[Point], start: datetime, end: datetime) -> list[Forecast]:
        start = start.astimezone(timezone.utc)
        hours = max(1, int((end - start).total_seconds() // 3600) + 2)
        out: list[Forecast] = []
        for point in points:
            samples = [self._field(point, float(h)) for h in range(hours)]
            out.append(
                Forecast(
                    start_epoch=int(start.timestamp()),
                    wind_mph=[s.wind_mph for s in samples],
                    rain_in_hr=[s.rain_in_hr for s in samples],
                    snow_in_hr=[s.snow_in_hr for s in samples],
                    temp_c=[s.temp_c for s in samples],
                    code=[s.code for s in samples],
                )
            )
        return out


def get_weather_provider():
    if settings.WEATHER_PROVIDER == "synthetic":
        return SyntheticWeather()
    return OpenMeteoWeather()


__all__ = [
    "Forecast",
    "WeatherSample",
    "OpenMeteoWeather",
    "SyntheticWeather",
    "get_weather_provider",
    "UpstreamError",
]
