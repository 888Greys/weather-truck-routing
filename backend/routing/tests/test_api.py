import json
from datetime import timedelta

import pytest
from django.test import Client, override_settings
from django.utils import timezone


@pytest.fixture
def client():
    return Client()


def payload(**overrides):
    body = {
        "origin": {"lat": -1.2921, "lon": 36.8219, "label": "Nairobi"},
        "destination": {"lat": -4.0435, "lon": 39.6682, "label": "Mombasa"},
        "depart_at": (timezone.now() + timedelta(hours=2)).isoformat(),
        "weight_lb": 42000,
        "sample_interval_miles": 25,
    }
    body.update(overrides)
    return body


def post(client, body):
    return client.post("/api/plan/", data=json.dumps(body), content_type="application/json")


@override_settings(ROUTING_PROVIDER="synthetic", WEATHER_PROVIDER="synthetic")
def test_plan_happy_path(client):
    response = post(client, payload())
    assert response.status_code == 200
    body = response.json()
    assert len(body["routes"]) == 3
    assert body["recommendation"]["route_id"]
    assert body["legend"][0]["label"] == "Low"


@override_settings(ROUTING_PROVIDER="synthetic", WEATHER_PROVIDER="synthetic")
def test_rejects_identical_endpoints(client):
    body = payload()
    body["destination"] = body["origin"]
    response = post(client, body)
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_request"


@override_settings(ROUTING_PROVIDER="synthetic", WEATHER_PROVIDER="synthetic")
def test_rejects_bad_interval(client):
    response = post(client, payload(sample_interval_miles=17))
    assert response.status_code == 400


@override_settings(ROUTING_PROVIDER="synthetic", WEATHER_PROVIDER="synthetic")
def test_rejects_departure_beyond_forecast_horizon(client):
    response = post(client, payload(depart_at=(timezone.now() + timedelta(days=40)).isoformat()))
    assert response.status_code == 400


@override_settings(ROUTING_PROVIDER="synthetic", WEATHER_PROVIDER="synthetic")
def test_rejects_out_of_range_coordinates(client):
    response = post(client, payload(origin={"lat": 120, "lon": 36.8}))
    assert response.status_code == 400


def test_meta_endpoint(client):
    response = client.get("/api/meta/")
    assert response.status_code == 200
    body = response.json()
    assert body["limits"]["sample_intervals_miles"] == [10, 25, 50]
    assert len(body["legend"]) == 5


def test_geocode_requires_a_query(client):
    response = client.get("/api/geocode/", {"q": "a"})
    assert response.status_code == 200
    assert response.json()["results"] == []


def test_health(client):
    assert client.get("/health/").json() == {"status": "ok"}