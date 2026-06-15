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
from datetime import datetime, timezone

from sqlalchemy import select

from backend.futures_risk.execution import dispatch_order, load_broker_context_sync, log_event
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
# Exit placement
# ---------------------------------------------------------------------------

def _place_exit(trade: FrTrade, qty: int, reason: str) -> tuple[bool, str | None, str]:
    if qty <= 0:
        return True, None, "nothing to exit"
    exit_action = "SELL" if trade.side == "BUY" else "BUY"
    order_data = {
        "symbol": trade.option_symbol,
        "exchange": trade.option_exchange,
        "action": exit_action,
        "quantity": str(qty),
        "pricetype": "MARKET",
        "product": trade.product,
        "price": "0",
        "trigger_price": "0",
        "strategy": f"FuturesRisk-{reason}",
    }
    ok, resp, _status = dispatch_order(trade.mode, trade.user_id, order_data)
    if ok:
        return True, resp.get("orderid"), "ok"
    return False, None, resp.get("message", "exit failed")


# ---------------------------------------------------------------------------
# Trailing
# ---------------------------------------------------------------------------

def _apply_trailing(trade: FrTrade, all_targets: list[FrTradeTarget], hit_seq: int) -> None:
    """Move the SL after a target is hit, per the configured trailing mode."""
    if not fr_service._bool_cfg("trailing_enabled", True):
        return
    # Per-trade override (set via modify); falls back to the global config.
    mode = (trade.meta or {}).get("trailing_mode") or fr_service.get_config_value("trailing_mode", "entry_after_t1")
    if mode == "off":
        return

    new_price: float | None = None
    basis = trade.sl_basis
    if mode == "entry_after_t1":
        # After the first target, lock to cost-to-cost (entry futures price).
        new_price = trade.entry_futures_price
        basis = "entry"
    elif mode == "prev_target":
        if hit_seq <= 1:
            new_price = trade.entry_futures_price
            basis = "entry"
        else:
            prev = next((t for t in all_targets if t.seq == hit_seq - 1), None)
            if prev is not None:
                new_price = prev.trigger_price
                basis = f"target{hit_seq - 1}"

    if new_price is None:
        return
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
    # Snapshot the trade + targets.
    with session_scope() as db:
        t = db.get(FrTrade, trade_id)
        if t is None or t.status != "active":
            return
        user_id = t.user_id
        fut_symbol, fut_exchange = t.futures_symbol, t.futures_exchange

    ctx = ctx_cache.get(user_id, "missing")
    if ctx == "missing":
        ctx = load_broker_context_sync(user_id)
        ctx_cache[user_id] = ctx

    fut = _futures_price(fut_symbol, fut_exchange, ctx)
    if fut is None:
        return

    auto_exit = fr_service._bool_cfg("auto_exit_enabled", True)

    with session_scope() as db:
        t = db.get(FrTrade, trade_id)
        if t is None or t.status != "active":
            return
        all_targets = db.execute(
            select(FrTradeTarget).where(FrTradeTarget.trade_id == t.id).order_by(FrTradeTarget.seq)
        ).scalars().all()

        # --- Stop-loss: exits everything remaining ---
        if _sl_hit(t.direction, fut, t.sl_price):
            qty = t.remaining_qty
            if not auto_exit:
                return
            ok, oid, msg = _place_exit(t, qty, "sl") if qty > 0 else (True, None, "ok")
            if ok:
                t.remaining_qty = 0
                t.status = "stopped"
                log_event(
                    db, trade_id=t.id, user_id=user_id, kind="sl_hit", severity="warning",
                    message=f"Stop-loss hit at futures {fut} (SL {t.sl_price}, basis {t.sl_basis}); exited {qty}",
                    payload={"futures_price": fut, "exit_order_id": oid, "qty": qty},
                )
            else:
                log_event(
                    db, trade_id=t.id, user_id=user_id, kind="error", severity="error",
                    message=f"SL exit failed at futures {fut}: {msg}", payload={"futures_price": fut},
                )
            return

        # --- Targets: partial exits in sequence ---
        fired_any = False
        for tgt in all_targets:
            if tgt.status != "pending":
                continue
            if not _target_hit(t.direction, fut, tgt.trigger_price):
                continue
            if not auto_exit:
                continue
            qty = min(tgt.exit_qty, t.remaining_qty)
            ok, oid, msg = _place_exit(t, qty, f"t{tgt.seq}") if qty > 0 else (True, None, "ok")
            if not ok:
                log_event(
                    db, trade_id=t.id, user_id=user_id, kind="error", severity="error",
                    message=f"Target {tgt.seq} exit failed at futures {fut}: {msg}",
                    payload={"futures_price": fut, "seq": tgt.seq},
                )
                continue
            tgt.status = "hit"
            tgt.hit_futures_price = fut
            tgt.exit_order_id = oid
            tgt.hit_at = datetime.now(tz=timezone.utc)
            t.remaining_qty = max(0, t.remaining_qty - qty)
            fired_any = True
            log_event(
                db, trade_id=t.id, user_id=user_id, kind="target_hit",
                message=f"Target {tgt.seq} hit at futures {fut} (trigger {tgt.trigger_price}); exited {qty}",
                payload={"futures_price": fut, "seq": tgt.seq, "exit_order_id": oid, "qty": qty},
            )
            prev_sl = t.sl_price
            _apply_trailing(t, all_targets, tgt.seq)
            if t.sl_price != prev_sl:
                log_event(
                    db, trade_id=t.id, user_id=user_id, kind="sl_trail",
                    message=f"Stop-loss trailed to {t.sl_price} ({t.sl_basis}) after target {tgt.seq}",
                    payload={"sl_price": t.sl_price, "basis": t.sl_basis},
                )

        if t.remaining_qty <= 0 and t.status == "active":
            t.status = "completed"
            log_event(
                db, trade_id=t.id, user_id=user_id, kind="completed",
                message="All quantity exited via targets", payload={"futures_price": fut},
            )
        elif fired_any and all(x.status != "pending" for x in all_targets) and t.remaining_qty > 0:
            # All targets done but a remainder is still open — it now rides the
            # trailed SL. Nothing else to do this pass.
            pass


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
