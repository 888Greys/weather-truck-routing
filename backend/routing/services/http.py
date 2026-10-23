"""Tiny JSON-over-HTTPS client with retries.

Kept dependency-free on purpose: the deployment target is a free tier and the
whole surface is a handful of GETs, so `urllib` plus a retry loop is enough and
keeps the container image small.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


class UpstreamError(RuntimeError):
    """A third-party API failed in a way the caller may want to degrade around."""


def get_json(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    timeout: float | None = None,
    retries: int = 2,
    headers: dict[str, str] | None = None,
) -> Any:
    if params:
        url = f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode(params, doseq=True)}"
    timeout = timeout or settings.HTTP_TIMEOUT_SECONDS
    request_headers = {"User-Agent": settings.HTTP_USER_AGENT, "Accept": "application/json"}
    if headers:
        request_headers.update(headers)

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(url, headers=request_headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_error = exc
            # 4xx (except 429) will not get better by retrying.
            if exc.code < 500 and exc.code != 429:
                break
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            last_error = exc
        if attempt < retries:
            time.sleep(0.4 * (attempt + 1))

    raise UpstreamError(f"GET {url} failed: {last_error}") from last_error
