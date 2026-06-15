"""Shared SlowAPI limiter instance.

Defined in its own module so both `backend.main` (which registers the
exception handler) and route modules (which use `@limiter.limit(...)`
decorators) can import it without circular dependencies.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.config import get_settings

_settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    # In-memory storage: a local single-instance app doesn't need a shared
    # Redis-backed limiter, and a flaky/unreachable Redis must never turn a
    # rate-limited endpoint (login, orders) into a 500.
    storage_uri="memory://",
    # Defensive: if the storage backend ever errors, allow the request through
    # rather than raising — graceful degradation over hard failure.
    swallow_errors=True,
)
