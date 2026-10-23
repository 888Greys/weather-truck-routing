from rest_framework.throttling import SimpleRateThrottle


class BurstThrottle(SimpleRateThrottle):
    """Per-IP burst protection so a public demo cannot burn the weather quota."""

    scope = "burst"

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
