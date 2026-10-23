from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

SAMPLE_INTERVALS = (10, 25, 50)


class CoordinateSerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)
    label = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")


class PlanRequestSerializer(serializers.Serializer):
    origin = CoordinateSerializer()
    destination = CoordinateSerializer()
    depart_at = serializers.DateTimeField()
    weight_lb = serializers.FloatField(min_value=0, max_value=120_000)
    sample_interval_miles = serializers.ChoiceField(choices=SAMPLE_INTERVALS, required=False, default=25)
    horizon_hours = serializers.IntegerField(min_value=1, max_value=48, required=False, default=48)
    scenario = serializers.ChoiceField(choices=("live", "stress"), required=False, default="live")

    def validate_depart_at(self, value):
        now = timezone.now()
        if value < now - timedelta(days=2):
            raise serializers.ValidationError("Departure is more than two days in the past.")
        if value > now + timedelta(days=15):
            raise serializers.ValidationError(
                "Departure must be within 15 days - that is the limit of the hourly forecast feed."
            )
        return value

    def validate(self, attrs):
        origin, destination = attrs["origin"], attrs["destination"]
        same = abs(origin["lat"] - destination["lat"]) < 1e-4 and abs(origin["lon"] - destination["lon"]) < 1e-4
        if same:
            raise serializers.ValidationError("Origin and destination must be different places.")
        attrs["sample_interval_miles"] = float(attrs["sample_interval_miles"])
        return attrs
