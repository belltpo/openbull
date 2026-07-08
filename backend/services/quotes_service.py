"""
Quotes service - fetches LTP/OHLC quotes from broker APIs.
"""

import hashlib
import importlib
import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

_COOLDOWN_LOCK = threading.Lock()
_COOLDOWNS: dict[tuple[str, str], tuple[float, str, int]] = {}
_AUTH_COOLDOWN_SECONDS = 300.0
_RATE_COOLDOWN_SECONDS = 90.0


def _credential_key(broker: str, auth_token: str, config: dict | None) -> tuple[str, str]:
    client_id = ""
    if isinstance(config, dict):
        client_id = str(config.get("client_id") or config.get("clientId") or config.get("api_key") or "")
    material = f"{client_id}:{auth_token or ''}"
    digest = hashlib.sha256(material.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return (str(broker or "").lower(), digest)


def _cooldown_error(message: str) -> tuple[bool, int, float]:
    text = str(message or "").lower()
    if any(token in text for token in ("too many requests", "rate limit", "429")):
        return True, 429, _RATE_COOLDOWN_SECONDS
    if any(token in text for token in (
        "authentication failed",
        "token invalid",
        "invalid or expired",
        "unauthorized",
        "invalid_authentication",
        "401",
        "403",
        "807",
        "808",
    )):
        return True, 401, _AUTH_COOLDOWN_SECONDS
    return False, 500, 0.0


def _active_cooldown(
    broker: str, auth_token: str, config: dict | None,
) -> tuple[bool, dict[str, Any], int]:
    key = _credential_key(broker, auth_token, config)
    now = time.monotonic()
    with _COOLDOWN_LOCK:
        entry = _COOLDOWNS.get(key)
        if not entry:
            return False, {}, 200
        until, message, status_code = entry
        if until <= now:
            _COOLDOWNS.pop(key, None)
            return False, {}, 200
        retry_after = max(1, int(until - now))
    return True, {
        "status": "error",
        "message": message,
        "retry_after_seconds": retry_after,
    }, status_code


def _remember_cooldown(
    broker: str, auth_token: str, config: dict | None, message: str,
) -> int | None:
    should_cooldown, status_code, ttl = _cooldown_error(message)
    if not should_cooldown:
        return None
    key = _credential_key(broker, auth_token, config)
    until = time.monotonic() + ttl
    with _COOLDOWN_LOCK:
        _COOLDOWNS[key] = (until, message, status_code)
    logger.warning(
        "Pausing %s quote requests for %.0fs after broker error: %s",
        broker,
        ttl,
        message,
    )
    return status_code


def get_quotes_with_auth(
    symbol: str, exchange: str, auth_token: str, broker: str, config: dict | None = None
) -> tuple[bool, dict[str, Any], int]:
    """Get quotes for a single symbol."""
    cooling_down, payload, status_code = _active_cooldown(broker, auth_token, config)
    if cooling_down:
        return False, payload, status_code

    try:
        data_module = importlib.import_module(f"backend.broker.{broker}.api.data")
    except ImportError:
        return False, {"status": "error", "message": "Broker module not found"}, 404

    try:
        result = data_module.get_quotes(symbol, exchange, auth_token, config)
        return True, {"status": "success", "data": result}, 200
    except ValueError as e:
        message = str(e)
        return False, {"status": "error", "message": message}, _remember_cooldown(broker, auth_token, config, message) or 400
    except Exception as e:
        message = str(e)
        logger.error("Error fetching quotes: %s", message)
        return False, {"status": "error", "message": message}, _remember_cooldown(broker, auth_token, config, message) or 500


def get_multi_quotes_with_auth(
    symbols_list: list[dict], auth_token: str, broker: str, config: dict | None = None
) -> tuple[bool, dict[str, Any], int]:
    """Get quotes for multiple symbols."""
    cooling_down, payload, status_code = _active_cooldown(broker, auth_token, config)
    if cooling_down:
        return False, payload, status_code

    try:
        data_module = importlib.import_module(f"backend.broker.{broker}.api.data")
    except ImportError:
        return False, {"status": "error", "message": "Broker module not found"}, 404

    try:
        results = data_module.get_multi_quotes(symbols_list, auth_token, config)
        # OpenAlgo returns the list under "results" (not "data"); match that contract.
        return True, {"status": "success", "results": results}, 200
    except ValueError as e:
        message = str(e)
        return False, {"status": "error", "message": message}, _remember_cooldown(broker, auth_token, config, message) or 400
    except Exception as e:
        message = str(e)
        logger.error("Error fetching multi quotes: %s", message)
        return False, {"status": "error", "message": message}, _remember_cooldown(broker, auth_token, config, message) or 500
