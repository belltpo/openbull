"""Shared SlowAPI limiter instance.

Defined in its own module so both `backend.main` (which registers the
exception handler) and route modules (which use `@limiter.limit(...)`
decorators) can import it without circular dependencies.
"""
from slowapi import Limiter
from starlette.requests import Request

from backend.config import get_settings
from backend.utils.client_ip import client_ip

_settings = get_settings()


def _rate_limit_key(request: Request) -> str:
    """Per-client rate-limit key.

    slowapi's ``get_remote_address`` reads ``request.client.host``. The
    shipped systemd unit serves uvicorn over a unix socket, so
    ``request.client`` is None for *every* request and slowapi fell back to a
    single constant key — meaning the login limits (5/min, 25/hour) were one
    global bucket shared by all callers, and any one client could lock
    everybody out of login.

    backend.utils.client_ip resolves the real address from forwarded headers,
    but only when the peer is a configured trusted proxy, so this cannot be
    turned into a limit bypass by sending a fake header.
    """
    return client_ip(request) or "unknown"


limiter = Limiter(
    key_func=_rate_limit_key,
    # In-memory storage: a local single-instance app doesn't need a shared
    # Redis-backed limiter, and a flaky/unreachable Redis must never turn a
    # rate-limited endpoint (login, orders) into a 500.
    storage_uri="memory://",
    # Defensive: if the storage backend ever errors, allow the request through
    # rather than raising — graceful degradation over hard failure.
    swallow_errors=True,
)
