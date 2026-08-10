"""Broker-position reconciliation for Futures-Risk live trades.

The important contract in this module is that an API error is never treated
as a zero position.  A confirmed empty/missing broker position is represented
by ``ok=True, quantity=0``; authentication, transport, and malformed responses
are represented by ``ok=False`` and must fail closed.  Dhan is parsed from its
raw response so its error envelopes can never be normalised into an empty list.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_TTL_SEC = 5.0
_cache: dict[tuple[str, str], tuple[float, Any]] = {}
_cache_lock = threading.Lock()
_fetch_locks: dict[tuple[str, str], threading.Lock] = {}


@dataclass(frozen=True)
class PositionSnapshot:
    supported: bool
    ok: bool
    quantity: int | None = None
    message: str | None = None
    broker_pnl: float | None = None


@dataclass(frozen=True)
class ReconciliationDecision:
    action: str
    broker_quantity: int
    message: str | None = None


def decide_position_reconciliation(
    recorded_quantity: int,
    side: str,
    broker_signed_quantity: int,
) -> ReconciliationDecision:
    """Pure safety policy for a broker/OpenBull quantity comparison."""
    recorded = max(0, int(recorded_quantity or 0))
    signed = int(broker_signed_quantity or 0)
    broker_qty = abs(signed)
    if signed == 0:
        return ReconciliationDecision("closed", 0)
    expected_sign = 1 if str(side).upper() == "BUY" else -1
    if signed * expected_sign < 0:
        return ReconciliationDecision(
            "blocked",
            broker_qty,
            f"Broker position direction ({signed}) conflicts with OpenBull trade side {side}",
        )
    if broker_qty > recorded:
        return ReconciliationDecision(
            "blocked",
            broker_qty,
            f"Broker has {broker_qty} qty but OpenBull records {recorded}; automatic exit is paused to avoid an oversized order",
        )
    if broker_qty < recorded:
        return ReconciliationDecision("adjusted", broker_qty)
    return ReconciliationDecision("unchanged", broker_qty)


def _auth_cache_key(broker: str, auth_token: str) -> tuple[str, str]:
    # Do not retain or log the token itself.  hash() is process-local and is
    # sufficient for this short-lived in-memory cache.
    return broker.lower(), str(hash(auth_token))


def invalidate_position_cache(broker: str, auth_token: str) -> None:
    with _cache_lock:
        _cache.pop(_auth_cache_key(broker, auth_token), None)


def _raw_positions(ctx: dict[str, Any], *, force: bool) -> tuple[bool, Any, str | None]:
    broker = str(ctx.get("broker") or "").lower()
    auth_token = str(ctx.get("auth_token") or "")
    if not auth_token:
        return True, None, "No active broker session"
    key = _auth_cache_key(broker, auth_token)
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(key)
        if not force and cached and now - cached[0] < _CACHE_TTL_SEC:
            return True, cached[1], None
        fetch_lock = _fetch_locks.setdefault(key, threading.Lock())

    with fetch_lock:
        now = time.monotonic()
        with _cache_lock:
            cached = _cache.get(key)
            if not force and cached and now - cached[0] < _CACHE_TTL_SEC:
                return True, cached[1], None
        try:
            if broker == "dhan":
                from backend.broker.dhan.api.order_api import get_positions

                raw = get_positions(auth_token)
            else:
                from backend.services.positions_service import get_positions_with_auth

                ok, response, _ = get_positions_with_auth(
                    auth_token,
                    broker,
                    ctx.get("config"),
                )
                if not ok:
                    return True, None, str(response.get("message") or "Broker positions request failed")
                raw = response.get("data")
        except Exception as exc:
            logger.exception("%s position reconciliation request failed", broker)
            return True, None, str(exc)
        if not isinstance(raw, list):
            if isinstance(raw, dict):
                message = (
                    raw.get("errorMessage")
                    or raw.get("message")
                    or raw.get("remarks")
                    or raw.get("errorType")
                )
            else:
                message = None
            return True, None, str(message or f"{broker} returned an invalid positions response")
        with _cache_lock:
            _cache[key] = (time.monotonic(), raw)
        return True, raw, None


def dhan_position_from_rows(
    rows: list[dict[str, Any]],
    *,
    symbol: str,
    exchange: str,
    product: str,
) -> PositionSnapshot:
    """Return a strict, signed Dhan position match from a validated row list."""
    from backend.broker.dhan.mapping.transform_data import map_exchange_type, map_product_type
    from backend.broker.upstox.mapping.order_data import (
        get_brsymbol_from_cache,
        get_token_from_cache,
    )

    def _normalise(value: Any) -> str:
        return str(value or "").strip().upper()

    def _token(value: Any) -> str:
        # The shared cache can carry a broker-token suffix. Dhan positions use
        # only the securityId at the start of that composite value.
        return _normalise(value).split("::::", 1)[0]

    broker_symbol = get_brsymbol_from_cache(symbol, exchange)
    symbol_candidates = {_normalise(symbol), _normalise(broker_symbol)} - {""}
    expected_token = _token(get_token_from_cache(symbol, exchange))
    broker_exchange = _normalise(map_exchange_type(exchange))
    broker_product = _normalise(map_product_type(product))
    saw_authoritative_token = False
    for row in rows:
        if _normalise(row.get("exchangeSegment")) != broker_exchange:
            continue
        if _normalise(row.get("productType")) != broker_product:
            continue
        row_symbol = _normalise(row.get("tradingSymbol"))
        row_token = _token(row.get("securityId"))
        saw_authoritative_token = saw_authoritative_token or bool(row_token)
        symbol_match = bool(row_symbol and row_symbol in symbol_candidates)
        token_match = bool(expected_token and row_token and row_token == expected_token)
        if symbol_match or token_match:
            try:
                quantity = int(float(row.get("netQty") or 0))
            except (TypeError, ValueError):
                return PositionSnapshot(True, False, message="Dhan returned an invalid net quantity")
            try:
                broker_pnl = float(row.get("realizedProfit") or 0) + float(row.get("unrealizedProfit") or 0)
            except (TypeError, ValueError):
                broker_pnl = None
            return PositionSnapshot(True, True, quantity=quantity, broker_pnl=broker_pnl)

    if rows and not (expected_token and saw_authoritative_token):
        # A non-empty raw Dhan book with no reliable identifier mapping is not
        # proof that this contract is closed. Only a broker book containing
        # security IDs plus our expected security ID can prove an authoritative
        # absence. Treat every other mapping miss as unknown instead of
        # silently converting a symbol-cache problem into a zero position.
        return PositionSnapshot(
            True,
            False,
            message=(
                f"Dhan position for {exchange}:{symbol} could not be matched safely; "
                "refresh the master contract before automatic reconciliation"
            ),
        )
    return PositionSnapshot(True, True, quantity=0, broker_pnl=0.0)


def get_position_snapshot(trade: Any, ctx: dict[str, Any] | None, *, force: bool = False) -> PositionSnapshot:
    if ctx is None:
        return PositionSnapshot(True, False, message="No active broker session")
    broker = str(ctx.get("broker") or "").lower()
    supported, rows, error = _raw_positions(ctx, force=force)
    if error:
        return PositionSnapshot(supported, False, message=error)
    if broker == "dhan":
        return dhan_position_from_rows(
            rows,
            symbol=trade.option_symbol,
            exchange=trade.option_exchange,
            product=trade.product,
        )
    for row in rows:
        if (
            str(row.get("symbol") or "").upper() == str(trade.option_symbol).upper()
            and str(row.get("exchange") or "").upper() == str(trade.option_exchange).upper()
            and str(row.get("product") or "").upper() == str(trade.product).upper()
        ):
            try:
                quantity = int(float(row.get("quantity") or 0))
            except (TypeError, ValueError):
                return PositionSnapshot(True, False, message=f"{broker} returned an invalid net quantity")
            try:
                broker_pnl = float(row.get("pnl")) if row.get("pnl") is not None else None
            except (TypeError, ValueError):
                broker_pnl = None
            return PositionSnapshot(True, True, quantity=quantity, broker_pnl=broker_pnl)
    return PositionSnapshot(True, True, quantity=0, broker_pnl=0.0)
