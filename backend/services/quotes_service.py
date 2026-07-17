"""Broker quote gateway.

Every quote request, including a one-symbol request, is sent through the
broker's multi-quote endpoint.  This gives Dhan one rate-limited upstream path
and lets concurrent page/Quick Order consumers share a short-lived result.
"""

import hashlib
import importlib
import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

_COOLDOWN_LOCK = threading.Lock()
_COOLDOWNS: dict[tuple[str, str], tuple[float, str, int, str]] = {}
_AUTH_COOLDOWN_SECONDS = 300.0
_RATE_COOLDOWN_SECONDS = 90.0

_QUOTE_LOCK = threading.Lock()
_QUOTE_CACHE: dict[tuple, tuple[float, list[dict[str, Any]]]] = {}
_QUOTE_INFLIGHT: dict[tuple, threading.Event] = {}
_QUOTE_CACHE_SECONDS = 0.85
_QUOTE_WAIT_SECONDS = 20.0


def _credential_key(broker: str, auth_token: str, config: dict | None) -> tuple[str, str]:
    client_id = ""
    if isinstance(config, dict):
        client_id = str(config.get("client_id") or config.get("clientId") or config.get("api_key") or "")
    material = f"{client_id}:{auth_token or ''}"
    digest = hashlib.sha256(material.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return (str(broker or "").lower(), digest)


def _cooldown_error(message: str) -> tuple[bool, int, float, str]:
    text = str(message or "").lower()
    if any(token in text for token in ("too many requests", "rate limit", "429", "805")):
        return True, 429, _RATE_COOLDOWN_SECONDS, "BROKER_RATE_LIMIT"
    if any(token in text for token in (
        "authentication failed", "token invalid", "invalid or expired",
        "unauthorized", "invalid_authentication", "401", "403", "807", "808", "810",
    )):
        return True, 401, _AUTH_COOLDOWN_SECONDS, "BROKER_AUTH_REQUIRED"
    return False, 500, 0.0, "BROKER_ERROR"


def _issue_payload(
    broker: str, message: str, code: str, retry_after: int | None = None,
) -> dict[str, Any]:
    guidance = (
        f"{str(broker or 'Broker').title()} data rate limit reached. "
        "Regenerate or re-login the broker API connection in Broker Configuration."
        if code == "BROKER_RATE_LIMIT"
        else f"{str(broker or 'Broker').title()} authentication expired. Re-login in Broker Configuration."
        if code == "BROKER_AUTH_REQUIRED"
        else str(message or "Broker quote request failed")
    )
    payload: dict[str, Any] = {
        "status": "error",
        "code": code,
        "broker": str(broker or "").lower(),
        "message": guidance,
        "broker_message": str(message or ""),
        "requires_broker_reauth": code in {"BROKER_RATE_LIMIT", "BROKER_AUTH_REQUIRED"},
        "action_url": "/broker/config",
    }
    if retry_after is not None:
        payload["retry_after_seconds"] = max(1, int(retry_after))
    return payload


def _active_cooldown(
    broker: str, auth_token: str, config: dict | None,
) -> tuple[bool, dict[str, Any], int]:
    key = _credential_key(broker, auth_token, config)
    now = time.monotonic()
    with _COOLDOWN_LOCK:
        entry = _COOLDOWNS.get(key)
        if not entry:
            return False, {}, 200
        until, message, status_code, code = entry
        if until <= now:
            _COOLDOWNS.pop(key, None)
            return False, {}, 200
        retry_after = max(1, int(until - now))
    return True, _issue_payload(broker, message, code, retry_after), status_code


def _remember_cooldown(
    broker: str, auth_token: str, config: dict | None, message: str,
) -> tuple[int | None, str]:
    should_cooldown, status_code, ttl, code = _cooldown_error(message)
    if not should_cooldown:
        return None, code
    key = _credential_key(broker, auth_token, config)
    until = time.monotonic() + ttl
    with _COOLDOWN_LOCK:
        _COOLDOWNS[key] = (until, message, status_code, code)
    logger.warning("Pausing %s quote requests for %.0fs after broker error: %s", broker, ttl, message)
    return status_code, code


def _dedupe_symbols(symbols_list: list[dict]) -> list[dict[str, str]]:
    unique: dict[tuple[str, str], dict[str, str]] = {}
    for item in symbols_list or []:
        symbol = str(item.get("symbol") or "").strip().upper()
        exchange = str(item.get("exchange") or "").strip().upper()
        if symbol and exchange:
            unique.setdefault((exchange, symbol), {"symbol": symbol, "exchange": exchange})
    return list(unique.values())


def _normalize_rows(rows: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw in rows if isinstance(rows, list) else []:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        nested = row.get("data")
        if isinstance(nested, dict):
            for key, value in nested.items():
                row.setdefault(key, value)
        normalized.append(row)
    return normalized


def _quote_cache_key(
    symbols: list[dict[str, str]], broker: str, auth_token: str, config: dict | None,
) -> tuple:
    return (_credential_key(broker, auth_token, config), tuple(sorted(
        (item["exchange"], item["symbol"]) for item in symbols
    )))


def get_multi_quotes_with_auth(
    symbols_list: list[dict], auth_token: str, broker: str, config: dict | None = None,
) -> tuple[bool, dict[str, Any], int]:
    """Fetch a deduplicated batch, coalescing simultaneous identical calls."""
    symbols = _dedupe_symbols(symbols_list)
    if not symbols:
        return True, {"status": "success", "results": []}, 200

    cooling_down, payload, status_code = _active_cooldown(broker, auth_token, config)
    if cooling_down:
        return False, payload, status_code

    key = _quote_cache_key(symbols, broker, auth_token, config)
    now = time.monotonic()
    leader = False
    with _QUOTE_LOCK:
        cached = _QUOTE_CACHE.get(key)
        if cached and cached[0] > now:
            return True, {"status": "success", "results": cached[1], "cached": True}, 200
        event = _QUOTE_INFLIGHT.get(key)
        if event is None:
            event = threading.Event()
            _QUOTE_INFLIGHT[key] = event
            leader = True

    if not leader:
        event.wait(_QUOTE_WAIT_SECONDS)
        with _QUOTE_LOCK:
            cached = _QUOTE_CACHE.get(key)
        if cached:
            return True, {"status": "success", "results": cached[1], "cached": True}, 200
        cooling_down, payload, status_code = _active_cooldown(broker, auth_token, config)
        if cooling_down:
            return False, payload, status_code
        return False, _issue_payload(broker, "Shared quote request timed out", "QUOTE_UNAVAILABLE"), 504

    try:
        try:
            data_module = importlib.import_module(f"backend.broker.{broker}.api.data")
        except ImportError:
            return False, _issue_payload(broker, "Broker module not found", "BROKER_MODULE_NOT_FOUND"), 404

        results = _normalize_rows(data_module.get_multi_quotes(symbols, auth_token, config))
        with _QUOTE_LOCK:
            _QUOTE_CACHE[key] = (time.monotonic() + _QUOTE_CACHE_SECONDS, results)
            # Bound process memory when many one-off search symbols are used.
            if len(_QUOTE_CACHE) > 2048:
                oldest = sorted(_QUOTE_CACHE.items(), key=lambda item: item[1][0])[:512]
                for old_key, _ in oldest:
                    _QUOTE_CACHE.pop(old_key, None)
        return True, {"status": "success", "results": results}, 200
    except Exception as exc:
        message = str(exc)
        logger.error("Error fetching multi quotes: %s", message)
        remembered_status, code = _remember_cooldown(broker, auth_token, config, message)
        status = remembered_status or (400 if isinstance(exc, ValueError) else 500)
        retry_after = int(_RATE_COOLDOWN_SECONDS if code == "BROKER_RATE_LIMIT" else _AUTH_COOLDOWN_SECONDS) if remembered_status else None
        return False, _issue_payload(broker, message, code, retry_after), status
    finally:
        with _QUOTE_LOCK:
            done = _QUOTE_INFLIGHT.pop(key, None)
            if done is not None:
                done.set()


def get_quotes_with_auth(
    symbol: str, exchange: str, auth_token: str, broker: str, config: dict | None = None,
) -> tuple[bool, dict[str, Any], int]:
    """Single-symbol compatibility API implemented via multi-quote only."""
    ok, response, status_code = get_multi_quotes_with_auth(
        [{"symbol": symbol, "exchange": exchange}], auth_token, broker, config,
    )
    if not ok:
        return False, response, status_code
    rows = response.get("results") or []
    if not rows:
        return False, _issue_payload(
            broker, f"No quote data available for {symbol}/{exchange}", "QUOTE_UNAVAILABLE",
        ), 404
    row = dict(rows[0])
    data = row.get("data") if isinstance(row.get("data"), dict) else {
        key: value for key, value in row.items() if key not in {"symbol", "exchange", "error"}
    }
    if row.get("error") and not data:
        return False, _issue_payload(broker, str(row["error"]), "QUOTE_UNAVAILABLE"), 502
    return True, {"status": "success", "data": data}, 200
