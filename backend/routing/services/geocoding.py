"""Forward geocoding through Nominatim, cached for a day."""
from __future__ import annotations

from django.conf import settings

from .cache import GEOCODE_TTL, memo
from .http import get_json


def search(query: str, limit: int = 5) -> list[dict]:
    query = query.strip()
    if len(query) < 2:
        return []

    def run() -> list[dict]:
        payload = get_json(
            f"{settings.NOMINATIM_BASE_URL.rstrip('/')}/search",
            {
                "q": query,
                "format": "jsonv2",
                "limit": limit,
                "addressdetails": 0,
            },
            headers={"Accept-Language": "en"},
        )
        results = []
        for item in payload if isinstance(payload, list) else []:
            try:
                results.append(
                    {
                        "label": item.get("display_name", query),
                        "name": item.get("name") or item.get("display_name", query).split(",")[0],
                        "lat": float(item["lat"]),
                        "lon": float(item["lon"]),
                        "type": item.get("type", ""),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue
        return results

    return memo("geocode", {"q": query.lower(), "limit": limit}, GEOCODE_TTL, run)
