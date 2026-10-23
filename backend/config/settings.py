"""Django settings for the weather-aware truck routing service.

Configuration is environment driven so the same settings module runs locally,
in CI, and on the free hosting tiers used for the assessment demo.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-secret-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "routing",
]

MIDDLEWARE = [
    "django.middleware.gzip.GZipMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.security.SecurityMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

# The app is stateless: results live in the cache, so no database is required to
# serve requests. SQLite keeps `manage.py check` and future admin work happy.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "routing-cache",
        "TIMEOUT": 60 * 30,
        "OPTIONS": {"MAX_ENTRIES": 5000},
    }
}

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_THROTTLE_CLASSES": ["routing.throttles.BurstThrottle"],
    "DEFAULT_THROTTLE_RATES": {"burst": os.environ.get("PLAN_THROTTLE_RATE", "30/min")},
}

CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "%(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}

# --- Application settings -------------------------------------------------
# Providers can be switched to deterministic fakes so tests, CI and an offline
# demo never depend on third-party uptime.
ROUTING_PROVIDER = os.environ.get("ROUTING_PROVIDER", "osrm")
WEATHER_PROVIDER = os.environ.get("WEATHER_PROVIDER", "open-meteo")
GEOCODING_PROVIDER = os.environ.get("GEOCODING_PROVIDER", "nominatim")

OSRM_BASE_URL = os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org")
NOMINATIM_BASE_URL = os.environ.get("NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org")
OPEN_METEO_BASE_URL = os.environ.get("OPEN_METEO_BASE_URL", "https://api.open-meteo.com")
HTTP_USER_AGENT = os.environ.get("HTTP_USER_AGENT", "weather-truck-routing/1.0 (assessment demo)")
HTTP_TIMEOUT_SECONDS = float(os.environ.get("HTTP_TIMEOUT_SECONDS", "20"))

# Forecast horizon exposed by the UI slider (hours from departure).
FORECAST_HORIZON_HOURS = int(os.environ.get("FORECAST_HORIZON_HOURS", "48"))
# Spacing of the heat-map corridor cells. Independent of the checkpoint spacing.
HEATMAP_SPACING_MILES = float(os.environ.get("HEATMAP_SPACING_MILES", "25"))
MAX_ROUTE_CHECKPOINTS = int(os.environ.get("MAX_ROUTE_CHECKPOINTS", "400"))
