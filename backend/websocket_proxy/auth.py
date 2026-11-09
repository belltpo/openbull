"""
Standalone API-key verification for the WebSocket proxy.

Shares the Redis cache namespace with backend.dependencies so HTTP auth and
WebSocket auth populate each other's caches — no duplicate DB lookups.
"""

import logging

from backend.dependencies import (
    _decrypt_ctx_payload,
    _encrypted_ctx_payload,
    _key_api_ctx,
    _key_api_invalid,
    _key_api_valid,
    _remember_invalid_key,
    _resolve_api_key_user_id,
)
from sqlalchemy import select

from backend.database import async_session
from backend.models.auth import BrokerAuth
from backend.models.broker_config import BrokerConfig
from backend.security import api_key_lookup, decrypt_value
from backend.utils.redis_client import cache_delete, cache_get_json, cache_set_json

logger = logging.getLogger(__name__)

# Shared TTLs with backend.dependencies — keep aligned
API_KEY_TTL = 900       # 15 min
INVALID_KEY_TTL = 300   # 5 min
API_CTX_TTL = 3600      # 1 hour


async def verify_api_key_standalone(
    api_key: str,
) -> tuple[int, str, str, dict]:
    """Verify an API key and return (user_id, auth_token, broker_name, broker_config).

    Raises ValueError on failure.

    Key resolution, negative caching and the cache-key layout are shared with
    :mod:`backend.dependencies` so the HTTP and WebSocket paths cannot drift
    apart again — in particular so that the indexed ``api_key_lookup``
    fast-reject applies here too. This endpoint is reachable
    *unauthenticated* through the public ``/ws`` route, so it was the most
    exposed caller of the old Argon2-per-attempt path.
    """
    key_hash = api_key_lookup(api_key)

    if await cache_get_json(_key_api_invalid(key_hash)) is not None:
        raise ValueError("Invalid API key")

    # Resolve user_id from Redis or DB
    user_id = await cache_get_json(_key_api_valid(key_hash))

    async with async_session() as db:
        if user_id is None:
            user_id = await _resolve_api_key_user_id(db, api_key, key_hash)
            if user_id is None:
                await _remember_invalid_key(key_hash)
                raise ValueError("Invalid API key")
            await cache_set_json(_key_api_valid(key_hash), user_id, API_KEY_TTL)

        # Full API context (shared with HTTP /api/v1/*). Ciphertext only.
        cached_ctx = await cache_get_json(_key_api_ctx(user_id))
        if cached_ctx:
            try:
                auth_token, broker_name, config = _decrypt_ctx_payload(cached_ctx)
                return (user_id, auth_token, broker_name, config)
            except Exception:
                logger.warning(
                    "api ctx cache entry unusable for user %s; refreshing", user_id
                )
                await cache_delete(_key_api_ctx(user_id))

        # Get broker auth
        result = await db.execute(
            select(BrokerAuth).where(
                BrokerAuth.user_id == user_id,
                BrokerAuth.is_revoked == False,
            )
        )
        broker_auth = result.scalar_one_or_none()
        if not broker_auth:
            raise ValueError("No active broker session")

        auth_token = decrypt_value(broker_auth.access_token)
        broker_name = broker_auth.broker_name

        # Get broker config
        result = await db.execute(
            select(BrokerConfig).where(
                BrokerConfig.user_id == user_id,
                BrokerConfig.broker_name == broker_name,
            )
        )
        broker_cfg = result.scalar_one_or_none()
        config = {}
        if broker_cfg:
            config = {
                "api_key": decrypt_value(broker_cfg.api_key),
                "api_secret": decrypt_value(broker_cfg.api_secret),
                "redirect_url": broker_cfg.redirect_url,
                # Dhan's streaming endpoint requires the trading Client ID in
                # addition to the app credentials.  Keep this payload aligned
                # with backend.dependencies.get_broker_context, which is used
                # by the HTTP quote/order paths.
                "client_id": (broker_cfg.extra_config or {}).get("client_id"),
            }

        await cache_set_json(
            _key_api_ctx(user_id),
            _encrypted_ctx_payload(broker_name, broker_auth, broker_cfg),
            API_CTX_TTL,
        )

        return (user_id, auth_token, broker_name, config)
