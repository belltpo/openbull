"""Rate limiting for the external ``/api/v1`` surface.

``API_RATE_LIMIT`` ("50 per second") and ``ORDER_RATE_LIMIT``
("10 per second") existed in :mod:`backend.config` but were referenced
nowhere — ``@limiter.limit`` was applied to four auth routes only, so every
one of the 36 ``/api/v1`` modules, including order placement, was unlimited.
That also meant an unauthenticated caller could drive the API-key
verification path (an Argon2 hash, ~64 MB and tens of milliseconds) as fast
as it could send requests, against a single-worker uvicorn.

Applied as middleware rather than per-route decorators so no endpoint can be
added later and silently miss the limit. Keyed on the resolved client IP
(see :mod:`backend.utils.client_ip`) with an in-process fixed window, which
matches the existing slowapi configuration: single worker, memory storage,
and fail-open if anything goes wrong — a limiter must never take down order
placement.
"""

from __future__ import annotations

import logging
import re
import threading
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.config import get_settings
from backend.utils.client_ip import client_ip

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1/"

# Order-placing endpoints get the tighter ORDER_RATE_LIMIT. Matched on the
# path tail, mirroring backend.middleware_api_log.TRADE_ENDPOINTS.
ORDER_ENDPOINTS = frozenset(
    {
        "placeorder",
        "placesmartorder",
        "modifyorder",
        "cancelorder",
        "cancelallorder",
        "closeposition",
        "basketorder",
        "splitorder",
        "optionsorder",
        "optionsmultiorder",
    }
)

_PERIODS = {
    "second": 1,
    "minute": 60,
    "hour": 3600,
    "day": 86400,
}


def parse_limit(spec: str, default: tuple[int, int]) -> tuple[int, int]:
    """Parse "N per <period>" into (count, window_seconds)."""
    match = re.match(r"\s*(\d+)\s*per\s*(second|minute|hour|day)\s*$", spec or "", re.I)
    if not match:
        logger.warning("Unparseable rate limit %r — using %s/%ss", spec, *default)
        return default
    return int(match.group(1)), _PERIODS[match.group(2).lower()]


class _FixedWindow:
    """Tiny in-process fixed-window counter. Thread-safe, bounded in size."""

    #: Hard cap on tracked keys so unauthenticated traffic from many source
    #: addresses cannot grow this dict without bound.
    MAX_KEYS = 10_000

    def __init__(self) -> None:
        self._hits: dict[tuple[str, int], int] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window: int) -> bool:
        bucket = int(time.time() // window)
        with self._lock:
            if len(self._hits) > self.MAX_KEYS:
                # Drop everything outside the current window, then give up on
                # tracking if it is still oversized (fail open).
                self._hits = {
                    k: v for k, v in self._hits.items() if k[1] == bucket
                }
                if len(self._hits) > self.MAX_KEYS:
                    return True
            count = self._hits.get((key, bucket), 0) + 1
            self._hits[(key, bucket)] = count
            return count <= limit


class ApiRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        settings = get_settings()
        self._api_limit = parse_limit(settings.api_rate_limit, (50, 1))
        self._order_limit = parse_limit(settings.order_rate_limit, (10, 1))
        self._window = _FixedWindow()
        logger.info(
            "ApiRateLimitMiddleware: api=%d/%ss order=%d/%ss",
            self._api_limit[0], self._api_limit[1],
            self._order_limit[0], self._order_limit[1],
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if request.method == "OPTIONS" or not path.startswith(API_PREFIX):
            return await call_next(request)

        try:
            tail = path[len(API_PREFIX):].strip("/")
            is_order = tail in ORDER_ENDPOINTS
            limit, window = self._order_limit if is_order else self._api_limit
            key = f"{'order' if is_order else 'api'}:{client_ip(request) or 'unknown'}"
            allowed = self._window.allow(key, limit, window)
        except Exception:
            # Never let the limiter break the API.
            logger.debug("rate limit check failed; allowing", exc_info=True)
            return await call_next(request)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"status": "error", "message": "Rate limit exceeded"},
                headers={"Retry-After": str(window)},
            )
        return await call_next(request)


__all__ = ["ApiRateLimitMiddleware", "parse_limit"]
