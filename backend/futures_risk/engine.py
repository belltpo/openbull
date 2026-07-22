"""
Futures-Risk auto-exit engine.

A background daemon thread that, every ``poll_interval_sec``, walks all active
trades, reads the underlying futures price (MarketDataCache first, broker-quote
fallback), and fires partial/full exits when a target or the stop-loss is hit.
Trailing moves the SL to cost-to-cost after Target 1 (configurable).

Modeled on ``backend.sandbox.mtm_updater`` / ``execution_engine`` (sync DB,
daemon thread, stop-event loop).
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from backend.futures_risk.execution import load_broker_context_sync, log_event
from backend.futures_risk import service as fr_service
from backend.models.futures_risk import FrTrade, FrTradeTarget
from backend.sandbox._db import session_scope
from backend.services.market_data_cache import get_ltp_value
from backend.services.quotes_service import get_quotes_with_auth

logger = logging.getLogger(__name__)

_stop_event = threading.Event()
_thread: threading.Thread | None = None
_running = False


# ---------------------------------------------------------------------------
# Server-side streaming hint
# ---------------------------------------------------------------------------

def ensure_streaming(symbol: str, exchange: str) -> None:
    """Best-effort: ask the broker WS adapter to keep this futures symbol
    streaming so its ticks land in MarketDataCache. We always have a broker-
    quote fallback, so failure here is non-fatal."""
    try:
        from backend.websocket_proxy import server as ws_server

        adapter = getattr(ws_server, "_adapter", None)
        if adapter is None:
            return
        adapter.subscribe([{"symbol": symbol, "exchange": exchange}], 1)  # 1 = MODE_LTP
        logger.debug("Futures-Risk: requested stream for %s/%s", symbol, exchange)
    except Exception:
        logger.debug("ensure_streaming failed for %s/%s", symbol, exchange, exc_info=True)


def ensure_symbols_streaming(symbols: list[dict[str, str]]) -> None:
    """Best-effort subscription for every distinct Futures-Risk leg.

    A position's rupee P&L is driven by its option premium while target/SL
    evaluation is driven by its futures contract.  Both legs therefore need
    to stay in MarketDataCache; subscribing only the future leaves MTM static.
    """
    seen: set[tuple[str, str]] = set()
    for item in symbols or []:
        symbol = str(item.get("symbol") or "").strip()
        exchange = str(item.get("exchange") or "").strip()
        key = (symbol.upper(), exchange.upper())
        if not symbol or not exchange or key in seen:
            continue
        seen.add(key)
        ensure_streaming(symbol, exchange)


# ---------------------------------------------------------------------------
# Price source
# ---------------------------------------------------------------------------

def _futures_price(symbol: str, exchange: str, ctx: dict | None) -> float | None:
    """Cache-first futures LTP with a broker-quote fallback."""
    val = get_ltp_value(symbol, exchange)
    if val and val > 0:
        return float(val)
    if ctx is None:
        return None
    try:
        ok, q, _ = get_quotes_with_auth(symbol, exchange, ctx["auth_token"], ctx["broker"], ctx["config"])
        if ok:
            ltp = q.get("data", {}).get("ltp")
            if ltp and float(ltp) > 0:
                return float(ltp)
    except Exception:
        logger.debug("futures quote fallback failed for %s", symbol, exc_info=True)
    return None


# ---------------------------------------------------------------------------
# Trailing
# ---------------------------------------------------------------------------

def _trade_trailing_mode(trade: FrTrade) -> str:
    raw = (trade.meta or {}).get("trailing_mode") or fr_service.get_config_value("trailing_mode", "entry_after_t1")
    mode = str(raw or "entry_after_t1").strip()
    return mode if mode in {"entry_after_t1", "prev_target", "off"} else "entry_after_t1"


def _apply_trailing(trade: FrTrade, hit_seq: int, targets: list[FrTradeTarget]) -> None:
    if hit_seq < 1 or not fr_service._bool_cfg("trailing_enabled", True):
        return
    mode = _trade_trailing_mode(trade)
    if mode == "off":
        return
    if mode == "prev_target" and hit_seq > 1:
        prev_target = next((target for target in targets if target.seq == hit_seq - 1), None)
        new_price = prev_target.trigger_price if prev_target is not None else trade.entry_futures_price
        basis = f"target{hit_seq - 1}" if prev_target is not None else "entry"
    else:
        new_price = trade.entry_futures_price
        basis = "entry"
    # Only ever tighten in the favourable direction (never loosen the SL).
    improved = (
        (trade.direction == 1 and new_price > trade.sl_price)
        or (trade.direction == -1 and new_price < trade.sl_price)
    )
    if improved:
        trade.sl_price = round(new_price, 2)
        trade.sl_basis = basis


# ---------------------------------------------------------------------------
# Per-trade evaluation
# ---------------------------------------------------------------------------

def _sl_hit(direction: int, fut: float, sl_price: float) -> bool:
    return (direction == 1 and fut <= sl_price) or (direction == -1 and fut >= sl_price)


def _target_hit(direction: int, fut: float, trigger: float) -> bool:
    return (direction == 1 and fut >= trigger) or (direction == -1 and fut <= trigger)


def _process_trade(trade_id: int, ctx_cache: dict[int, dict | None]) -> None:
    """Evaluate one trade through the persistent, single-flight exit path."""
    with session_scope() as db:
        trade = db.get(FrTrade, trade_id)
        if trade is None or trade.status != "active":
            return
        user_id = trade.user_id
        mode = trade.mode
        created_at = trade.created_at
        fut_symbol, fut_exchange = trade.futures_symbol, trade.futures_exchange
        option_symbol, option_exchange = trade.option_symbol, trade.option_exchange

    ensure_symbols_streaming([
        {"symbol": fut_symbol, "exchange": fut_exchange},
        {"symbol": option_symbol, "exchange": option_exchange},
    ])
    ctx = ctx_cache.get(user_id, "missing")
    if ctx == "missing":
        ctx = load_broker_context_sync(user_id)
        ctx_cache[user_id] = ctx

    if mode == "live" and ctx is not None:
        created = created_at
        if created is not None and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created is None or datetime.now(tz=timezone.utc) - created >= timedelta(seconds=10):
            try:
                fr_service.reconcile_trade(user_id, trade_id, ctx=ctx, force=False)
            except fr_service.FrError:
                # Passive checks fail closed and silently; an actual exit uses
                # a forced fresh snapshot and persists any blocking reason.
                pass

    with session_scope() as db:
        trade = db.get(FrTrade, trade_id)
        if (
            trade is None
            or trade.status != "active"
            or fr_service._exit_state(trade) != "idle"
        ):
            return

    fut = _futures_price(fut_symbol, fut_exchange, ctx)
    if fut is None or not fr_service._bool_cfg("auto_exit_enabled", True):
        return

    sl_qty: int | None = None
    target_seq: int | None = None
    target_qty: int | None = None
    with session_scope() as db:
        trade = db.get(FrTrade, trade_id)
        if (
            trade is None
            or trade.status != "active"
            or fr_service._exit_state(trade) != "idle"
        ):
            return
        targets = db.execute(
            select(FrTradeTarget)
            .where(FrTradeTarget.trade_id == trade.id)
            .order_by(FrTradeTarget.seq)
        ).scalars().all()
        if _sl_hit(trade.direction, fut, trade.sl_price):
            sl_qty = int(trade.remaining_qty or 0)
        else:
            for target in targets:
                if target.status != "pending" or not _target_hit(
                    trade.direction, fut, target.trigger_price
                ):
                    continue
                final_pending = not any(
                    row.status == "pending" and row.seq > target.seq for row in targets
                )
                planned = max(target.exit_qty, trade.remaining_qty) if final_pending else target.exit_qty
                qty = min(int(planned or 0), int(trade.remaining_qty or 0))
                if qty <= 0:
                    target.status = "hit"
                    target.hit_futures_price = fut
                    target.hit_at = datetime.now(tz=timezone.utc)
                    log_event(
                        db,
                        trade_id=trade.id,
                        user_id=user_id,
                        kind="target_hit",
                        message=(
                            f"Target {target.seq} reached at futures {fut}; no quantity exited because "
                            "the configured percentage is below one executable lot"
                        ),
                        payload={"futures_price": fut, "seq": target.seq, "qty": 0},
                    )
                    previous_sl = trade.sl_price
                    _apply_trailing(trade, target.seq, targets)
                    if trade.sl_price != previous_sl:
                        log_event(
                            db,
                            trade_id=trade.id,
                            user_id=user_id,
                            kind="sl_trail",
                            message=f"Stop-loss trailed to {trade.sl_price} ({trade.sl_basis}) after target {target.seq}",
                            payload={"sl_price": trade.sl_price, "basis": trade.sl_basis},
                        )
                    continue
                target_seq, target_qty = target.seq, qty
                break

    if sl_qty:
        fr_service.execute_trade_exit(
            trade_id,
            user_id=None,
            requested_qty=sl_qty,
            reason="sl",
            ctx=ctx,
            futures_price=fut,
        )
        return
    if target_seq is None or target_qty is None:
        return
    result = fr_service.execute_trade_exit(
        trade_id,
        user_id=None,
        requested_qty=target_qty,
        reason=f"t{target_seq}",
        ctx=ctx,
        futures_price=fut,
        target_seq=target_seq,
    )
    if not result.ok or result.reconciled:
        return
    with session_scope() as db:
        trade = db.get(FrTrade, trade_id)
        if trade is None:
            return
        targets = db.execute(
            select(FrTradeTarget)
            .where(FrTradeTarget.trade_id == trade.id)
            .order_by(FrTradeTarget.seq)
        ).scalars().all()
        previous_sl = trade.sl_price
        _apply_trailing(trade, target_seq, targets)
        if trade.sl_price != previous_sl:
            log_event(
                db,
                trade_id=trade.id,
                user_id=trade.user_id,
                kind="sl_trail",
                message=f"Stop-loss trailed to {trade.sl_price} ({trade.sl_basis}) after target {target_seq}",
                payload={"sl_price": trade.sl_price, "basis": trade.sl_basis},
            )


# ---------------------------------------------------------------------------
# Loop
# ---------------------------------------------------------------------------

def _active_trade_ids() -> list[int]:
    with session_scope() as db:
        rows = db.execute(select(FrTrade.id).where(FrTrade.status == "active")).all()
        return [r[0] for r in rows]


def _loop() -> None:
    logger.info("Futures-Risk auto-exit engine started")
    while not _stop_event.is_set():
        try:
            interval = max(1, int(float(fr_service.get_config_value("poll_interval_sec", "2"))))
        except Exception:
            interval = 2
        try:
            ids = _active_trade_ids()
            if ids:
                ctx_cache: dict[int, dict | None] = {}
                for tid in ids:
                    if _stop_event.is_set():
                        break
                    try:
                        _process_trade(tid, ctx_cache)
                    except Exception:
                        logger.exception("Futures-Risk: processing trade %s failed", tid)
        except Exception:
            logger.exception("Futures-Risk engine loop iteration failed")
        _stop_event.wait(interval)
    logger.info("Futures-Risk auto-exit engine stopped")


def start() -> None:
    global _thread, _running
    if _running:
        return
    _stop_event.clear()
    _running = True
    _thread = threading.Thread(target=_loop, name="futures-risk-engine", daemon=True)
    _thread.start()


def stop() -> None:
    global _running
    if not _running:
        return
    _stop_event.set()
    _running = False
