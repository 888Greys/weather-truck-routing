from __future__ import annotations

import logging

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import PlanRequestSerializer
from .services import geocoding, risk
from .services.geo import Point
from .services.http import UpstreamError
from .services.planner import PlanInput, build_plan

logger = logging.getLogger(__name__)


class PlanView(APIView):
    """POST /api/plan/ - the single call the map screen needs."""

    def post(self, request):
        serializer = PlanRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": "invalid_request", "detail": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        payload = PlanInput(
            origin=Point(data["origin"]["lat"], data["origin"]["lon"]),
            destination=Point(data["destination"]["lat"], data["destination"]["lon"]),
            depart_at=data["depart_at"],
            weight_lb=data["weight_lb"],
            spacing_miles=data["sample_interval_miles"],
            horizon_hours=data["horizon_hours"],
            origin_label=data["origin"].get("label", ""),
            destination_label=data["destination"].get("label", ""),
            scenario=data["scenario"],
        )
        try:
            result = build_plan(payload)
        except UpstreamError as exc:
            logger.warning("Upstream failure during plan: %s", exc)
            return Response(
                {
                    "error": "upstream_unavailable",
                    "detail": "The routing or weather provider did not respond. Try again in a moment.",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except ValueError as exc:
            return Response({"error": "unroutable", "detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        return Response(result)


class GeocodeView(APIView):
    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        if len(query) < 2:
            return Response({"results": []})
        try:
            results = geocoding.search(query)
        except UpstreamError:
            return Response(
                {"error": "upstream_unavailable", "detail": "Geocoding is temporarily unavailable."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({"results": results})


class MetaView(APIView):
    def get(self, request):
        return Response(
            {
                "providers": {
                    "routing": settings.ROUTING_PROVIDER,
                    "weather": settings.WEATHER_PROVIDER,
                    "geocoding": settings.GEOCODING_PROVIDER,
                },
                "limits": {
                    "sample_intervals_miles": [10, 25, 50],
                    "horizon_hours": settings.FORECAST_HORIZON_HOURS,
                    "max_weight_lb": 120000,
                },
                "legend": risk.risk_color_legend(),
            }
        )
