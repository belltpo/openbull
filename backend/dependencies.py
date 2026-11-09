import logging
import time
from typing import AsyncGenerator

from fastapi import Request, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import async_session
from backend.models.user import User
from backend.models.auth import BrokerAuth, ApiKey
from backend.models.audit import ActiveSession
from backend.models.broker_config import BrokerConfig
from backend.security import (
    api_key_lookup,
    decode_access_token,
    decrypt_value,
    verify_api_key,
)
from backend.utils.redis_client import (
    cache_delete,
    cache_delete_pattern,
    cache_get_json,
    cache_incr,
    cache_set_json,
)

logger = logging.getLogger(__name__)

# -- Cache TTLs (seconds) --
API_KEY_TTL = 900         # 15 min
INVALID_KEY_TTL = 300     # 5 min
# Cap on how many distinct rejected API keys get negative-cached per minute,
# so anonymous traffic cannot grow Redis memory without bound.
MAX_INVALID_KEYS_CACHED_PER_MIN = 256
BROKER_CTX_TTL = 3600     # 1 hour
API_CTX_TTL = 3600        # 1 hour


def _key_api_valid(key_hash: str) -> str:
    return f"api_key:valid:{key_hash}"


def _key_api_invalid(key_hash: str) -> str:
    return f"api_key:invalid:{key_hash}"


def _key_broker_ctx(user_id: int) -> str:
    # v3: the cached payload holds Fernet *ciphertext* rather than decrypted
    # credentials. The version bump guarantees an entry written by an older
    # build is never read back and mistaken for ciphertext.
    return f"broker_ctx:v3:{user_id}"


def _encrypted_ctx_payload(broker_name: str, broker_auth, broker_cfg) -> dict:
    """Build the cache payload, keeping every secret in its encrypted form.

    Redis has no password and no TLS in the shipped configuration, and its
    RDB snapshot sits on disk, so caching decrypted broker tokens and
    api_secrets put live brokerage credentials in cleartext outside the
    database. We cache exactly what the database stores — ciphertext — and
    decrypt per use. Fernet decryption is microseconds; the cache still saves
    the DB round-trips it was added for.
    """
    return {
        "broker_name": broker_name,
        "auth_token_enc": broker_auth.access_token,
        "config_enc": (
            {
                "api_key_enc": broker_cfg.api_key,
                "api_secret_enc": broker_cfg.api_secret,
                "redirect_url": broker_cfg.redirect_url,
                "client_id": (broker_cfg.extra_config or {}).get("client_id"),
            }
            if broker_cfg
            else None
        ),
    }


def _decrypt_ctx_payload(cached: dict) -> tuple[str, str, dict]:
    """Inverse of :func:`_encrypted_ctx_payload`. Raises if a value is stale."""
    auth_token = decrypt_value(cached["auth_token_enc"])
    cfg_enc = cached.get("config_enc")
    config: dict = {}
    if cfg_enc:
        config = {
            "api_key": decrypt_value(cfg_enc["api_key_enc"]),
            "api_secret": decrypt_value(cfg_enc["api_secret_enc"]),
            "redirect_url": cfg_enc.get("redirect_url"),
            # client_id (e.g. Dhan) — required in order payloads for some brokers.
            "client_id": cfg_enc.get("client_id"),
        }
    return auth_token, cached["broker_name"], config


def _key_api_ctx(user_id: int) -> str:
    # v3 for the same reason as _key_broker_ctx: the payload is ciphertext
    # now. Kept identical to backend.websocket_proxy.auth so the HTTP and
    # WebSocket paths genuinely share one entry (they had drifted apart —
    # this module used "api_ctx:" while the proxy used "api_ctx:v2:").
    return f"api_ctx:v3:{user_id}"


async def invalidate_all_caches() -> None:
    """Clear all API key / broker context caches. Called on API key rotation or logout."""
    await cache_delete_pattern("api_key:*")
    await cache_delete_pattern("broker_ctx:*")
    await cache_delete_pattern("api_ctx:*")


async def invalidate_user_cache(user_id: int) -> None:
    """Clear cached broker context for a single user. Call on logout / re-auth."""
    await cache_delete(_key_broker_ctx(user_id), _key_api_ctx(user_id))


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Enforce server-side session revocation: the JWT's jti must match a
    # live ActiveSession row for this user. Logout (and "log out all
    # devices") deletes those rows, invalidating any outstanding cookies
    # even though the JWT itself is still cryptographically valid.
    jti = payload.get("jti")
    if not jti:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    session_result = await db.execute(
        select(ActiveSession).where(
            ActiveSession.user_id == int(user_id),
            ActiveSession.session_token == jti,
        )
    )
    if session_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=401, detail="Session revoked")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    # Attach broker info from JWT to user object for convenience
    user._broker = payload.get("broker")
    user._session_token = jti
    # Tell ApiLogMiddleware this request is authenticated — without this tag,
    # the middleware skips the row so unauthenticated noise never hits the DB.
    request.state.user_id = user.id
    request.state.auth_method = "session"
    return user


class BrokerContext:
    def __init__(self, user: User, auth_token: str, broker_name: str, broker_config: dict):
        self.user = user
        self.auth_token = auth_token
        self.broker_name = broker_name
        self.broker_config = broker_config


async def get_broker_context(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BrokerContext:
    # Try Redis first. The cached payload holds ciphertext only; decrypt here.
    cached = await cache_get_json(_key_broker_ctx(user.id))
    if cached:
        try:
            auth_token, cached_broker, config = _decrypt_ctx_payload(cached)
            return BrokerContext(
                user=user,
                auth_token=auth_token,
                broker_name=cached_broker,
                broker_config=config,
            )
        except Exception:
            # Unreadable/stale entry (key rotation, format drift) — fall
            # through to the database rather than failing the request.
            logger.warning("broker ctx cache entry unusable for user %s; refreshing", user.id)
            await cache_delete(_key_broker_ctx(user.id))

    broker_name = getattr(user, "_broker", None)

    # If JWT doesn't have broker claim (cookie domain mismatch after OAuth),
    # check DB for the active broker config
    if not broker_name:
        result = await db.execute(
            select(BrokerConfig).where(
                BrokerConfig.user_id == user.id,
                BrokerConfig.is_active == True,
            )
        )
        active_config = result.scalar_one_or_none()
        if active_config:
            broker_name = active_config.broker_name

    if not broker_name:
        raise HTTPException(status_code=403, detail="Broker not authenticated. Please complete broker login.")

    # Get broker auth token
    result = await db.execute(
        select(BrokerAuth).where(
            BrokerAuth.user_id == user.id,
            BrokerAuth.broker_name == broker_name,
            BrokerAuth.is_revoked == False,
        )
    )
    broker_auth = result.scalar_one_or_none()
    if not broker_auth:
        raise HTTPException(status_code=403, detail="Broker session expired or revoked")

    auth_token = decrypt_value(broker_auth.access_token)

    # Get broker config (API key, secret for some broker calls)
    result = await db.execute(
        select(BrokerConfig).where(
            BrokerConfig.user_id == user.id,
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
            # client_id (e.g. Dhan) — required in order payloads for some brokers.
            "client_id": (broker_cfg.extra_config or {}).get("client_id"),
        }

    await cache_set_json(
        _key_broker_ctx(user.id),
        _encrypted_ctx_payload(broker_name, broker_auth, broker_cfg),
        BROKER_CTX_TTL,
    )

    return BrokerContext(user=user, auth_token=auth_token, broker_name=broker_name, broker_config=config)


async def _resolve_api_key_user_id(
    db: AsyncSession, provided_key: str, key_hash: str
) -> int | None:
    """Resolve an API key to a user id, Argon2-verifying at most one row.

    The indexed ``api_key_lookup`` fingerprint narrows to a single candidate,
    so a bogus key costs one SELECT rather than an Argon2 verification per
    stored key. Argon2 still decides whether the key is actually valid, so a
    forged fingerprint buys nothing.

    Rows whose ``api_key_lookup`` is NULL (pre-upgrade, or undecryptable at
    backfill time) are still handled by the original full-scan path, so the
    change cannot lock anyone out.
    """
    result = await db.execute(
        select(ApiKey).where(ApiKey.api_key_lookup == key_hash)
    )
    candidate = result.scalar_one_or_none()
    if candidate is not None:
        if verify_api_key(provided_key, candidate.api_key_hash):
            return candidate.user_id
        # Fingerprint matched but Argon2 did not: treat as invalid rather
        # than falling through to the scan.
        return None

    # Legacy fallback: only rows that have no fingerprint yet.
    result = await db.execute(
        select(ApiKey).where(ApiKey.api_key_lookup.is_(None))
    )
    for ak in result.scalars().all():
        if verify_api_key(provided_key, ak.api_key_hash):
            # Opportunistically fill the fingerprint so the next request
            # takes the indexed path.
            ak.api_key_lookup = key_hash
            try:
                await db.commit()
            except Exception:
                await db.rollback()
            return ak.user_id
    return None


async def _remember_invalid_key(key_hash: str) -> None:
    """Negative-cache a rejected key, with a bound on how many we remember.

    The old code wrote one Redis entry per rejected key with no cap, so an
    unauthenticated caller could grow Redis memory by sending endless random
    keys. A counter keyed per minute caps how many distinct bad keys get
    remembered; past the cap we simply skip caching (correctness is
    unaffected — the next attempt just re-checks the database).
    """
    try:
        bucket = f"api_key:invalid:count:{int(time.time() // 60)}"
        seen = await cache_incr(bucket, ttl=INVALID_KEY_TTL)
        if seen is None or seen <= MAX_INVALID_KEYS_CACHED_PER_MIN:
            await cache_set_json(_key_api_invalid(key_hash), 1, INVALID_KEY_TTL)
    except Exception:
        logger.debug("negative api-key cache write failed", exc_info=True)


async def get_api_user_id(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> int:
    """Resolve an external API key to a user id.

    Some /api/v1 endpoints only need OpenBull identity, not a live broker
    session. Keep this separate so sandbox and read-only integrations do not
    fail just because broker streaming/auth context is unavailable.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    provided_key = body.get("apikey") or request.headers.get("X-API-KEY")
    if not provided_key:
        raise HTTPException(status_code=401, detail="API key required")

    key_hash = api_key_lookup(provided_key)

    # Fast reject from negative cache
    if await cache_get_json(_key_api_invalid(key_hash)) is not None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Positive cache: key_hash -> user_id
    user_id = await cache_get_json(_key_api_valid(key_hash))

    if user_id is None:
        user_id = await _resolve_api_key_user_id(db, provided_key, key_hash)
        if user_id is None:
            await _remember_invalid_key(key_hash)
            raise HTTPException(status_code=401, detail="Invalid API key")
        await cache_set_json(_key_api_valid(key_hash), user_id, API_KEY_TTL)

    # Tell ApiLogMiddleware this request is authenticated (external API call).
    request.state.user_id = user_id
    request.state.auth_method = "api_key"
    return int(user_id)


async def get_api_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> tuple[int, str, str, dict]:
    """Resolve API key to (user_id, auth_token, broker_name, broker_config).
    Used by external /api/v1/* endpoints that need broker access.
    """
    user_id = await get_api_user_id(request, db)

    # Try full api-context cache (saves 2 more DB hits). Secrets are stored
    # encrypted; decrypt on read — see _encrypted_ctx_payload.
    cached_ctx = await cache_get_json(_key_api_ctx(user_id))
    if cached_ctx:
        try:
            auth_token, broker_name, config = _decrypt_ctx_payload(cached_ctx)
            return (user_id, auth_token, broker_name, config)
        except Exception:
            logger.warning("api ctx cache entry unusable for user %s; refreshing", user_id)
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
        raise HTTPException(status_code=403, detail="No active broker session")

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
            "client_id": (broker_cfg.extra_config or {}).get("client_id"),
        }

    await cache_set_json(
        _key_api_ctx(user_id),
        _encrypted_ctx_payload(broker_name, broker_auth, broker_cfg),
        API_CTX_TTL,
    )

    return (user_id, auth_token, broker_name, config)
