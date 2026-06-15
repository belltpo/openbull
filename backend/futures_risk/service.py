"""
Futures-Risk service layer — config / target / symbol-map CRUD, option &
futures symbol resolution, and the place-trade orchestration.

Synchronous (shares ``session_scope`` with the engine). Quote/symbol lookups
reuse the existing option-symbol service helpers so we stay consistent with
the rest of OpenBull's symbology.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, text

from backend.futures_risk import defaults as fr_defaults
from backend.futures_risk.execution import dispatch_order, load_broker_context_sync, log_event
from backend.models.futures_risk import (
    FrConfig,
    FrSymbolMap,
    FrTargetLevel,
    FrTrade,
    FrTradeEvent,
    FrTradeTarget,
)
from backend.sandbox._db import session_scope
from backend.services.option_symbol_service import (
    _fetch_available_strikes,
    _find_atm,
    _find_near_month_futures,
    _format_strike,
    _lookup_option_in_db,
    _option_exchange_for,
    _parse_underlying,
    _quote_exchange_for,
    get_option_symbol,
)
from backend.services.quotes_service import get_quotes_with_auth

logger = logging.getLogger(__name__)


class FrError(Exception):
    """User-facing error with an HTTP status code."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

def seed_defaults() -> None:
    """Insert config / target / symbol-map defaults if missing. Idempotent."""
    try:
        with session_scope() as db:
            existing_keys = {
                r.key for r in db.execute(select(FrConfig)).scalars().all()
            }
            for key, (value, desc, editable) in fr_defaults.CONFIG_DEFAULTS.items():
                if key not in existing_keys:
                    db.add(FrConfig(key=key, value=value, description=desc, is_editable=editable))

            if db.execute(select(func.count(FrTargetLevel.id))).scalar() == 0:
                for seq, points, pct in fr_defaults.TARGET_DEFAULTS:
                    db.add(FrTargetLevel(seq=seq, points=points, exit_pct=pct, enabled=True))

            if db.execute(select(func.count(FrSymbolMap.id))).scalar() == 0:
                for und, uexch, fexch, lot, auto in fr_defaults.SYMBOL_MAP_DEFAULTS:
                    db.add(
                        FrSymbolMap(
                            underlying=und,
                            underlying_exchange=uexch,
                            futures_exchange=fexch,
                            lot_size=lot,
                            auto_resolve=auto,
                            enabled=True,
                        )
                    )
        logger.info("Futures-Risk defaults seeded")
    except Exception:
        logger.exception("Failed to seed Futures-Risk defaults")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def get_config_map() -> dict[str, dict[str, Any]]:
    with session_scope() as db:
        rows = db.execute(select(FrConfig)).scalars().all()
        return {
            r.key: {"value": r.value, "description": r.description or "", "is_editable": r.is_editable}
            for r in rows
        }


def get_config_value(key: str, default: str = "") -> str:
    with session_scope() as db:
        row = db.execute(select(FrConfig).where(FrConfig.key == key)).scalar_one_or_none()
        return row.value if row else default


def set_config(key: str, value: str) -> bool:
    with session_scope() as db:
        row = db.execute(select(FrConfig).where(FrConfig.key == key)).scalar_one_or_none()
        if row is None or not row.is_editable:
            return False
        row.value = value
    return True


def _bool_cfg(key: str, default: bool) -> bool:
    return get_config_value(key, "true" if default else "false").strip().lower() in ("true", "1", "yes", "on")


# ---------------------------------------------------------------------------
# Target template CRUD
# ---------------------------------------------------------------------------

def _target_to_dict(r: FrTargetLevel) -> dict[str, Any]:
    return {"id": r.id, "seq": r.seq, "points": r.points, "exit_pct": r.exit_pct, "enabled": r.enabled}


def list_targets(enabled_only: bool = False) -> list[dict[str, Any]]:
    with session_scope() as db:
        q = select(FrTargetLevel).order_by(FrTargetLevel.seq)
        if enabled_only:
            q = q.where(FrTargetLevel.enabled == True)  # noqa: E712
        return [_target_to_dict(r) for r in db.execute(q).scalars().all()]


def create_target(points: float, exit_pct: float, enabled: bool = True) -> dict[str, Any]:
    with session_scope() as db:
        max_seq = db.execute(select(func.max(FrTargetLevel.seq))).scalar() or 0
        row = FrTargetLevel(seq=int(max_seq) + 1, points=float(points), exit_pct=float(exit_pct), enabled=bool(enabled))
        db.add(row)
        db.flush()
        return _target_to_dict(row)


def update_target(target_id: int, fields: dict[str, Any]) -> dict[str, Any] | None:
    with session_scope() as db:
        row = db.get(FrTargetLevel, target_id)
        if row is None:
            return None
        if "points" in fields:
            row.points = float(fields["points"])
        if "exit_pct" in fields:
            row.exit_pct = float(fields["exit_pct"])
        if "enabled" in fields:
            row.enabled = bool(fields["enabled"])
        db.flush()
        return _target_to_dict(row)


def delete_target(target_id: int) -> bool:
    with session_scope() as db:
        row = db.get(FrTargetLevel, target_id)
        if row is None:
            return False
        db.delete(row)
        db.flush()
        # Re-sequence remaining rows to stay contiguous (1..n). Two-phase to
        # avoid colliding with the unique index on seq.
        remaining = db.execute(select(FrTargetLevel).order_by(FrTargetLevel.seq)).scalars().all()
        for i, r in enumerate(remaining, start=1):
            r.seq = 1000 + i
        db.flush()
        for i, r in enumerate(remaining, start=1):
            r.seq = i
    return True


# ---------------------------------------------------------------------------
# Symbol map CRUD
# ---------------------------------------------------------------------------

def _map_to_dict(r: FrSymbolMap) -> dict[str, Any]:
    return {
        "id": r.id,
        "underlying": r.underlying,
        "underlying_exchange": r.underlying_exchange,
        "futures_symbol": r.futures_symbol,
        "futures_exchange": r.futures_exchange,
        "lot_size": r.lot_size,
        "auto_resolve": r.auto_resolve,
        "enabled": r.enabled,
    }


def list_symbol_maps() -> list[dict[str, Any]]:
    with session_scope() as db:
        rows = db.execute(select(FrSymbolMap).order_by(FrSymbolMap.underlying)).scalars().all()
        return [_map_to_dict(r) for r in rows]


def create_symbol_map(data: dict[str, Any]) -> dict[str, Any]:
    underlying = str(data["underlying"]).strip().upper()
    with session_scope() as db:
        exists = db.execute(select(FrSymbolMap).where(FrSymbolMap.underlying == underlying)).scalar_one_or_none()
        if exists is not None:
            raise FrError(f"Mapping for {underlying} already exists", 409)
        row = FrSymbolMap(
            underlying=underlying,
            underlying_exchange=str(data.get("underlying_exchange", "NSE_INDEX")).upper(),
            futures_symbol=(data.get("futures_symbol") or None),
            futures_exchange=str(data.get("futures_exchange", "NFO")).upper(),
            lot_size=int(data.get("lot_size", 0) or 0),
            auto_resolve=bool(data.get("auto_resolve", True)),
            enabled=bool(data.get("enabled", True)),
        )
        db.add(row)
        db.flush()
        return _map_to_dict(row)


def update_symbol_map(map_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    with session_scope() as db:
        row = db.get(FrSymbolMap, map_id)
        if row is None:
            return None
        if "underlying" in data:
            row.underlying = str(data["underlying"]).strip().upper()
        if "underlying_exchange" in data:
            row.underlying_exchange = str(data["underlying_exchange"]).upper()
        if "futures_symbol" in data:
            row.futures_symbol = data["futures_symbol"] or None
        if "futures_exchange" in data:
            row.futures_exchange = str(data["futures_exchange"]).upper()
        if "lot_size" in data:
            row.lot_size = int(data["lot_size"] or 0)
        if "auto_resolve" in data:
            row.auto_resolve = bool(data["auto_resolve"])
        if "enabled" in data:
            row.enabled = bool(data["enabled"])
        db.flush()
        return _map_to_dict(row)


def delete_symbol_map(map_id: int) -> bool:
    with session_scope() as db:
        row = db.get(FrSymbolMap, map_id)
        if row is None:
            return False
        db.delete(row)
    return True


# ---------------------------------------------------------------------------
# Resolution helpers (futures, expiries, strikes)
# ---------------------------------------------------------------------------

def resolve_futures(underlying: str) -> dict[str, Any] | None:
    """Return {symbol, exchange, lot_size} for the underlying's futures contract.

    Uses the admin symbol map. ``auto_resolve`` picks the near-month FUT from
    the symtoken master; otherwise the configured ``futures_symbol`` is used.
    """
    underlying = underlying.strip().upper()
    with session_scope() as db:
        row = db.execute(
            select(FrSymbolMap).where(FrSymbolMap.underlying == underlying, FrSymbolMap.enabled == True)  # noqa: E712
        ).scalar_one_or_none()
        if row is None:
            return None
        fexch = row.futures_exchange
        lot = row.lot_size
        auto = row.auto_resolve
        fsym = row.futures_symbol

    if not auto and fsym:
        return {"symbol": fsym, "exchange": fexch, "lot_size": lot}

    fut = _find_near_month_futures(underlying, fexch)
    if not fut:
        # Fall back to an explicit symbol if one was configured.
        if fsym:
            return {"symbol": fsym, "exchange": fexch, "lot_size": lot}
        return None
    return {"symbol": fut["symbol"], "exchange": fut["exchange"], "lot_size": lot}


def list_expiries(underlying: str, underlying_exchange: str = "NSE_INDEX") -> list[dict[str, str]]:
    """Distinct option expiries for the underlying, sorted chronologically.

    Returns ``[{"display": "28-AUG-25", "value": "28AUG25"}, ...]``.
    """
    base, _ = _parse_underlying(underlying)
    options_exchange = _option_exchange_for(_quote_exchange_for(base, underlying_exchange))
    with session_scope() as db:
        rows = db.execute(
            text(
                "SELECT DISTINCT expiry FROM symtoken "
                "WHERE symbol LIKE :prefix AND exchange = :exch "
                "AND instrumenttype IN ('CE','PE') AND expiry IS NOT NULL AND expiry != ''"
            ),
            {"prefix": f"{base}%", "exch": options_exchange},
        ).fetchall()
    out: list[tuple[datetime, str]] = []
    for (exp,) in rows:
        try:
            d = datetime.strptime(exp, "%d-%b-%y")
        except (ValueError, TypeError):
            continue
        out.append((d, exp))
    out.sort(key=lambda t: t[0])
    result = []
    for _d, exp in out:
        value = exp.replace("-", "").upper()  # 28-AUG-25 -> 28AUG25
        result.append({"display": exp.upper(), "value": value})
    return result


def list_strikes(
    underlying: str,
    underlying_exchange: str,
    expiry: str,
    option_type: str,
    auth_token: str,
    broker: str,
    config: dict | None = None,
) -> dict[str, Any]:
    """Available strikes for (underlying, expiry, type) + the ATM strike."""
    base, _ = _parse_underlying(underlying)
    quote_exchange = _quote_exchange_for(base, underlying_exchange)
    options_exchange = _option_exchange_for(quote_exchange)
    strikes = _fetch_available_strikes(base, expiry.upper(), option_type.upper(), options_exchange)

    atm: float | None = None
    try:
        if quote_exchange in ("NSE_INDEX", "BSE_INDEX", "NSE", "BSE"):
            quote_symbol, q_exch = base, quote_exchange
        else:
            fut = _find_near_month_futures(base, quote_exchange)
            quote_symbol, q_exch = (fut["symbol"], fut["exchange"]) if fut else (base, quote_exchange)
        ok, q, _ = get_quotes_with_auth(quote_symbol, q_exch, auth_token, broker, config)
        if ok:
            ltp = q.get("data", {}).get("ltp")
            if ltp:
                atm = _find_atm(float(ltp), strikes)
    except Exception:
        logger.exception("ATM lookup failed for %s", underlying)
    return {"strikes": strikes, "atm": atm, "options_exchange": options_exchange}


# ---------------------------------------------------------------------------
# Place trade
# ---------------------------------------------------------------------------

def _resolve_option(
    underlying: str,
    underlying_exchange: str,
    expiry: str,
    option_type: str,
    side: str,
    strike: float | None,
    offset: str | None,
    auth_token: str,
    broker: str,
    config: dict | None,
) -> dict[str, Any]:
    base, _ = _parse_underlying(underlying)
    options_exchange = _option_exchange_for(_quote_exchange_for(base, underlying_exchange))

    if strike is not None and strike > 0:
        symbol = f"{base}{expiry.upper()}{_format_strike(float(strike))}{option_type.upper()}"
        details = _lookup_option_in_db(symbol, options_exchange)
        if not details:
            raise FrError(f"Option {symbol} not found on {options_exchange}", 404)
        return {
            "symbol": details["symbol"],
            "exchange": details["exchange"],
            "lotsize": details["lotsize"] or 1,
            "strike": details["strike"],
        }

    ok, res, status = get_option_symbol(
        underlying=underlying,
        exchange=underlying_exchange,
        expiry_date=expiry,
        offset=(offset or "ATM").upper(),
        option_type=option_type,
        auth_token=auth_token,
        broker=broker,
        config=config,
    )
    if not ok:
        raise FrError(res.get("message", "Failed to resolve option symbol"), status)
    return {
        "symbol": res["symbol"],
        "exchange": res["exchange"],
        "lotsize": res.get("lotsize") or 1,
        "strike": res.get("strike"),
    }


def _build_targets(
    entry_fut: float,
    direction: int,
    lots: int,
    lot_size: int,
    template: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Snapshot target rows: trigger price + whole-lot exit qty per target."""
    out: list[dict[str, Any]] = []
    lots_used = 0
    for t in template:
        points = float(t["points"])
        pct = float(t.get("exit_pct", 0))
        lots_i = int((lots * pct) // 100)  # floor to whole lots
        if lots_used + lots_i > lots:
            lots_i = max(0, lots - lots_used)
        lots_used += lots_i
        out.append(
            {
                "seq": int(t["seq"]),
                "points": points,
                "exit_pct": pct,
                "trigger_price": round(entry_fut + direction * points, 2),
                "exit_qty": lots_i * lot_size,
            }
        )
    return out


def _normalise_params(params: dict[str, Any]) -> dict[str, Any]:
    """Validate + normalise the raw place/draft params into a clean dict."""
    underlying = str(params.get("underlying", "")).strip().upper()
    if not underlying:
        raise FrError("underlying is required")
    option_type = str(params.get("option_type", "")).upper()
    if option_type not in ("CE", "PE"):
        raise FrError("option_type must be CE or PE")
    side = str(params.get("side", "")).upper()
    if side not in ("BUY", "SELL"):
        raise FrError("side must be BUY or SELL")
    expiry = str(params.get("expiry", "")).strip().upper().replace("-", "")
    if not expiry:
        raise FrError("expiry is required (e.g. 28AUG25)")
    lots = int(params.get("lots", 0) or 0)
    if lots < 1:
        raise FrError("lots must be >= 1")

    strike = params.get("strike")
    strike = float(strike) if strike not in (None, "", 0, "0") else None
    sl_points = params.get("sl_points")
    sl_points = float(sl_points) if sl_points not in (None, "") else None

    return {
        "underlying": underlying,
        "underlying_exchange": str(params.get("underlying_exchange") or "NSE_INDEX").upper(),
        "option_type": option_type,
        "side": side,
        "expiry": expiry,
        "lots": lots,
        "product": str(params.get("product") or get_config_value("default_product", "MIS")).upper(),
        "strike": strike,
        "offset": params.get("offset") or "ATM",
        "sl_points": sl_points,
        "targets": params.get("targets") or None,
    }


def _resolve_trade_plan(
    auth_token: str,
    broker: str,
    config: dict | None,
    p: dict[str, Any],
    *,
    require_price: bool = True,
) -> dict[str, Any]:
    """Resolve option leg, futures contract, entry futures price, direction,
    SL and target snapshot for a (normalised) params dict.

    ``require_price=False`` (drafts) tolerates a missing live futures price by
    falling back to 0.0 so a draft can still be saved pre-market; the real
    price is re-read when the draft is placed.
    """
    # 1) Option leg
    opt = _resolve_option(
        p["underlying"], p["underlying_exchange"], p["expiry"], p["option_type"],
        p["side"], p["strike"], p["offset"], auth_token, broker, config,
    )

    # 2) Futures contract + entry futures price
    fut = resolve_futures(p["underlying"])
    if fut is None:
        raise FrError(
            f"No futures mapping configured for {p['underlying']}. Add one in the admin panel.", 400
        )
    entry_fut = 0.0
    ok, q, status = get_quotes_with_auth(fut["symbol"], fut["exchange"], auth_token, broker, config)
    if ok:
        ltp = q.get("data", {}).get("ltp")
        entry_fut = float(ltp) if ltp and float(ltp) > 0 else 0.0
    if entry_fut <= 0:
        if require_price:
            raise FrError(f"Futures price unavailable for {fut['symbol']}", 502)

    # Best-effort entry option price (for P&L display)
    entry_opt = 0.0
    try:
        ok2, oq, _ = get_quotes_with_auth(opt["symbol"], opt["exchange"], auth_token, broker, config)
        if ok2:
            entry_opt = float(oq.get("data", {}).get("ltp") or 0.0)
    except Exception:
        pass

    # 3) Direction + SL + targets
    direction = 1 if (p["option_type"] == "CE") == (p["side"] == "BUY") else -1
    sl_points = p["sl_points"]
    if sl_points is None:
        sl_points = float(get_config_value("default_sl_points", "30"))
    sl_price = round(entry_fut - direction * sl_points, 2) if entry_fut > 0 else 0.0

    if p["targets"]:
        template = [
            {"seq": i + 1, "points": float(t["points"]), "exit_pct": float(t.get("exit_pct", 0))}
            for i, t in enumerate(p["targets"])
            if float(t.get("points", 0)) > 0
        ]
    else:
        template = list_targets(enabled_only=True)
    if not template:
        raise FrError("No targets configured. Add target levels in the admin panel.", 400)
    lot_size = int(opt["lotsize"] or 1)
    target_rows = _build_targets(entry_fut, direction, p["lots"], lot_size, template)

    return {
        "option_symbol": opt["symbol"],
        "option_exchange": opt["exchange"],
        "strike_val": opt["strike"],
        "lot_size": lot_size,
        "total_qty": p["lots"] * lot_size,
        "fut_symbol": fut["symbol"],
        "fut_exchange": fut["exchange"],
        "entry_fut": entry_fut,
        "entry_opt": entry_opt,
        "direction": direction,
        "sl_points": sl_points,
        "sl_price": sl_price,
        "target_rows": target_rows,
    }


def _persist_targets(db, trade_id: int, target_rows: list[dict[str, Any]]) -> None:
    for tr in target_rows:
        db.add(
            FrTradeTarget(
                trade_id=trade_id,
                seq=tr["seq"],
                points=tr["points"],
                exit_pct=tr["exit_pct"],
                trigger_price=tr["trigger_price"],
                exit_qty=tr["exit_qty"],
                status="pending",
            )
        )


def place_trade(
    user_id: int,
    mode: str,
    auth_token: str,
    broker: str,
    config: dict | None,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Resolve symbols, read the entry futures price, place the entry option
    order, and persist the trade + target snapshot. Returns the trade dict.

    Raises ``FrError`` on validation / resolution / placement failure.
    """
    p = _normalise_params(params)
    plan = _resolve_trade_plan(auth_token, broker, config, p, require_price=True)

    # Place the entry order
    order_data = {
        "symbol": plan["option_symbol"],
        "exchange": plan["option_exchange"],
        "action": p["side"],
        "quantity": str(plan["total_qty"]),
        "pricetype": "MARKET",
        "product": p["product"],
        "price": "0",
        "trigger_price": "0",
        "strategy": "FuturesRisk",
    }
    ok, resp, status = dispatch_order(mode, user_id, order_data, auth_token=auth_token, broker=broker, config=config)
    if not ok:
        raise FrError(resp.get("message", "Entry order failed"), status)
    entry_order_id = resp.get("orderid")

    with session_scope() as db:
        trade = FrTrade(
            user_id=user_id,
            mode=mode,
            underlying=p["underlying"],
            option_symbol=plan["option_symbol"],
            option_exchange=plan["option_exchange"],
            option_type=p["option_type"],
            side=p["side"],
            product=p["product"],
            expiry=p["expiry"],
            strike=plan["strike_val"],
            lots=p["lots"],
            lot_size=plan["lot_size"],
            total_qty=plan["total_qty"],
            remaining_qty=plan["total_qty"],
            entry_option_price=plan["entry_opt"],
            entry_order_id=str(entry_order_id) if entry_order_id else None,
            futures_symbol=plan["fut_symbol"],
            futures_exchange=plan["fut_exchange"],
            entry_futures_price=plan["entry_fut"],
            direction=plan["direction"],
            sl_points=plan["sl_points"],
            sl_price=plan["sl_price"],
            sl_basis="initial",
            status="active",
            created_by=user_id,
            meta={"offset": p["offset"] if p["strike"] is None else None, "params": p},
        )
        db.add(trade)
        db.flush()
        _persist_targets(db, trade.id, plan["target_rows"])
        log_event(
            db,
            trade_id=trade.id,
            user_id=user_id,
            kind="entry",
            message=f"{p['side']} {p['lots']} lot(s) {plan['option_symbol']} @ MKT | entry futures {plan['entry_fut']} | SL {plan['sl_price']}",
            payload={"entry_order_id": entry_order_id, "futures": plan["fut_symbol"], "entry_futures_price": plan["entry_fut"]},
        )
        trade_id = trade.id

    try:
        from backend.futures_risk import engine as fr_engine

        fr_engine.ensure_streaming(plan["fut_symbol"], plan["fut_exchange"])
    except Exception:
        logger.debug("ensure_streaming skipped", exc_info=True)

    return get_trade(user_id, trade_id) or {}


# ---------------------------------------------------------------------------
# Draft positions (created/edited before order placement)
# ---------------------------------------------------------------------------

def create_draft(
    user_id: int,
    auth_token: str,
    broker: str,
    config: dict | None,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Create an editable draft position WITHOUT placing any order.

    Resolves the option/futures symbols and a preview SL/target snapshot off
    the current futures price (best-effort). Nothing is sent to the broker; the
    auto-exit engine ignores ``draft`` rows. Place it later with ``place_draft``.
    """
    p = _normalise_params(params)
    plan = _resolve_trade_plan(auth_token, broker, config, p, require_price=False)

    with session_scope() as db:
        trade = FrTrade(
            user_id=user_id,
            mode="live",  # set for real at placement time
            underlying=p["underlying"],
            option_symbol=plan["option_symbol"],
            option_exchange=plan["option_exchange"],
            option_type=p["option_type"],
            side=p["side"],
            product=p["product"],
            expiry=p["expiry"],
            strike=plan["strike_val"],
            lots=p["lots"],
            lot_size=plan["lot_size"],
            total_qty=plan["total_qty"],
            remaining_qty=plan["total_qty"],
            entry_option_price=plan["entry_opt"],
            entry_order_id=None,
            futures_symbol=plan["fut_symbol"],
            futures_exchange=plan["fut_exchange"],
            entry_futures_price=plan["entry_fut"],
            direction=plan["direction"],
            sl_points=plan["sl_points"],
            sl_price=plan["sl_price"],
            sl_basis="initial",
            status="draft",
            created_by=user_id,
            meta={"offset": p["offset"] if p["strike"] is None else None, "params": p},
        )
        db.add(trade)
        db.flush()
        _persist_targets(db, trade.id, plan["target_rows"])
        log_event(
            db, trade_id=trade.id, user_id=user_id, kind="draft_created",
            message=f"Draft {p['side']} {p['lots']} lot(s) {plan['option_symbol']} (preview SL {plan['sl_price']})",
            payload={"params": p},
        )
        trade_id = trade.id
    return get_trade(user_id, trade_id) or {}


def place_draft(
    user_id: int,
    mode: str,
    auth_token: str,
    broker: str,
    config: dict | None,
    trade_id: int,
) -> dict[str, Any]:
    """Promote a draft to a live/sandbox trade: re-resolve against the current
    futures price, place the entry order, and flip the row to ``active``."""
    with session_scope() as db:
        t = db.get(FrTrade, trade_id)
        if t is None or t.user_id != user_id:
            raise FrError("Draft not found", 404)
        if t.status != "draft":
            raise FrError(f"Trade is {t.status}, not a draft", 409)
        p = dict((t.meta or {}).get("params") or {})
    if not p:
        raise FrError("Draft is missing its parameters; recreate it", 422)

    p = _normalise_params(p)
    plan = _resolve_trade_plan(auth_token, broker, config, p, require_price=True)

    order_data = {
        "symbol": plan["option_symbol"],
        "exchange": plan["option_exchange"],
        "action": p["side"],
        "quantity": str(plan["total_qty"]),
        "pricetype": "MARKET",
        "product": p["product"],
        "price": "0",
        "trigger_price": "0",
        "strategy": "FuturesRisk",
    }
    ok, resp, status = dispatch_order(mode, user_id, order_data, auth_token=auth_token, broker=broker, config=config)
    if not ok:
        raise FrError(resp.get("message", "Entry order failed"), status)
    entry_order_id = resp.get("orderid")

    with session_scope() as db:
        t = db.get(FrTrade, trade_id)
        t.mode = mode
        t.option_symbol = plan["option_symbol"]
        t.option_exchange = plan["option_exchange"]
        t.strike = plan["strike_val"]
        t.lot_size = plan["lot_size"]
        t.total_qty = plan["total_qty"]
        t.remaining_qty = plan["total_qty"]
        t.entry_option_price = plan["entry_opt"]
        t.entry_order_id = str(entry_order_id) if entry_order_id else None
        t.futures_symbol = plan["fut_symbol"]
        t.futures_exchange = plan["fut_exchange"]
        t.entry_futures_price = plan["entry_fut"]
        t.direction = plan["direction"]
        t.sl_points = plan["sl_points"]
        t.sl_price = plan["sl_price"]
        t.sl_basis = "initial"
        t.status = "active"
        t.modified_by = user_id
        # Rebuild target snapshot off the real entry price.
        db.execute(
            text("DELETE FROM fr_trade_target WHERE trade_id = :tid"), {"tid": trade_id}
        )
        _persist_targets(db, trade_id, plan["target_rows"])
        log_event(
            db, trade_id=trade_id, user_id=user_id, kind="entry",
            message=f"Draft placed: {p['side']} {p['lots']} lot(s) {plan['option_symbol']} @ MKT | entry futures {plan['entry_fut']} | SL {plan['sl_price']}",
            payload={"entry_order_id": entry_order_id, "entry_futures_price": plan["entry_fut"]},
        )

    try:
        from backend.futures_risk import engine as fr_engine

        fr_engine.ensure_streaming(plan["fut_symbol"], plan["fut_exchange"])
    except Exception:
        logger.debug("ensure_streaming skipped", exc_info=True)

    return get_trade(user_id, trade_id) or {}


# ---------------------------------------------------------------------------
# Reads / serialization
# ---------------------------------------------------------------------------

def _trade_to_dict(t: FrTrade) -> dict[str, Any]:
    return {
        "id": t.id,
        "mode": t.mode,
        "underlying": t.underlying,
        "option_symbol": t.option_symbol,
        "option_exchange": t.option_exchange,
        "option_type": t.option_type,
        "side": t.side,
        "product": t.product,
        "expiry": t.expiry,
        "strike": t.strike,
        "lots": t.lots,
        "lot_size": t.lot_size,
        "total_qty": t.total_qty,
        "remaining_qty": t.remaining_qty,
        "entry_option_price": t.entry_option_price,
        "entry_order_id": t.entry_order_id,
        "futures_symbol": t.futures_symbol,
        "futures_exchange": t.futures_exchange,
        "entry_futures_price": t.entry_futures_price,
        "direction": t.direction,
        "sl_points": t.sl_points,
        "sl_price": t.sl_price,
        "sl_basis": t.sl_basis,
        "status": t.status,
        "realized_pnl": t.realized_pnl,
        "created_by": t.created_by,
        "modified_by": t.modified_by,
        "params": (t.meta or {}).get("params"),
        "trailing_mode": (t.meta or {}).get("trailing_mode"),
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def _target_row_to_dict(r: FrTradeTarget) -> dict[str, Any]:
    return {
        "seq": r.seq,
        "points": r.points,
        "exit_pct": r.exit_pct,
        "trigger_price": r.trigger_price,
        "exit_qty": r.exit_qty,
        "status": r.status,
        "hit_futures_price": r.hit_futures_price,
        "exit_order_id": r.exit_order_id,
        "hit_at": r.hit_at.isoformat() if r.hit_at else None,
    }


def _event_to_dict(e: FrTradeEvent) -> dict[str, Any]:
    return {
        "id": e.id,
        "trade_id": e.trade_id,
        "ts": e.ts.isoformat() if e.ts else None,
        "kind": e.kind,
        "severity": e.severity,
        "message": e.message,
        "payload": e.payload,
    }


def list_trades(user_id: int, status: str | None = None) -> list[dict[str, Any]]:
    with session_scope() as db:
        q = select(FrTrade).where(FrTrade.user_id == user_id)
        if status and status != "all":
            q = q.where(FrTrade.status == status)
        q = q.order_by(FrTrade.created_at.desc())
        trades = db.execute(q).scalars().all()
        out = []
        for t in trades:
            d = _trade_to_dict(t)
            tgts = db.execute(
                select(FrTradeTarget).where(FrTradeTarget.trade_id == t.id).order_by(FrTradeTarget.seq)
            ).scalars().all()
            d["targets"] = [_target_row_to_dict(r) for r in tgts]
            out.append(d)
        return out


def get_trade(user_id: int, trade_id: int) -> dict[str, Any] | None:
    with session_scope() as db:
        t = db.get(FrTrade, trade_id)
        if t is None or t.user_id != user_id:
            return None
        d = _trade_to_dict(t)
        tgts = db.execute(
            select(FrTradeTarget).where(FrTradeTarget.trade_id == t.id).order_by(FrTradeTarget.seq)
        ).scalars().all()
        d["targets"] = [_target_row_to_dict(r) for r in tgts]
        events = db.execute(
            select(FrTradeEvent).where(FrTradeEvent.trade_id == t.id).order_by(FrTradeEvent.ts.desc()).limit(100)
        ).scalars().all()
        d["events"] = [_event_to_dict(e) for e in events]
        return d


def manual_exit(
    user_id: int,
    trade_id: int,
    qty: int | None = None,
    *,
    emergency: bool = False,
) -> dict[str, Any]:
    """Exit quantity of an active trade immediately.

    * ``qty=None`` → exit ALL remaining (full close).
    * ``qty=N``    → partial exit of N (capped at remaining). Trade stays
      ``active`` if a remainder is left.
    * ``emergency=True`` → forced full close, logged distinctly.
    """
    with session_scope() as db:
        t = db.get(FrTrade, trade_id)
        if t is None or t.user_id != user_id:
            raise FrError("Trade not found", 404)
        if t.status != "active":
            raise FrError(f"Trade is {t.status}, not active", 409)
        remaining = t.remaining_qty
        mode, side = t.mode, t.side
        option_symbol, option_exchange, product = t.option_symbol, t.option_exchange, t.product

    if emergency or qty is None:
        exit_qty = remaining
    else:
        exit_qty = max(0, min(int(qty), remaining))
        if exit_qty == 0:
            raise FrError("qty must be between 1 and the remaining quantity", 400)

    exit_order_id = None
    if exit_qty > 0:
        exit_action = "SELL" if side == "BUY" else "BUY"
        order_data = {
            "symbol": option_symbol,
            "exchange": option_exchange,
            "action": exit_action,
            "quantity": str(exit_qty),
            "pricetype": "MARKET",
            "product": product,
            "price": "0",
            "trigger_price": "0",
            "strategy": "FuturesRisk-exit",
        }
        ok, resp, status = dispatch_order(mode, user_id, order_data)
        if not ok:
            raise FrError(resp.get("message", "Exit order failed"), status)
        exit_order_id = resp.get("orderid")

    with session_scope() as db:
        t = db.get(FrTrade, trade_id)
        t.remaining_qty = max(0, t.remaining_qty - exit_qty)
        t.modified_by = user_id
        closed = t.remaining_qty <= 0
        if closed:
            t.status = "completed"
        if emergency:
            kind, msg = "emergency_exit", f"EMERGENCY exit of {exit_qty} qty {option_symbol}"
            sev = "warning"
        elif closed:
            kind, msg, sev = "completed", f"Manual full exit of {exit_qty} qty {option_symbol}", "info"
        else:
            kind, msg, sev = "partial_exit", f"Manual partial exit of {exit_qty} qty {option_symbol} ({t.remaining_qty} left)", "info"
        log_event(
            db, trade_id=t.id, user_id=user_id, kind=kind, severity=sev,
            message=msg, payload={"exit_order_id": exit_order_id, "qty": exit_qty, "remaining": t.remaining_qty},
        )
    return get_trade(user_id, trade_id) or {}


# ---------------------------------------------------------------------------
# Modify (draft or active) + delete
# ---------------------------------------------------------------------------

# Fields that may only be changed while a position is a draft (pre-placement).
_DRAFT_ONLY_FIELDS = {"underlying", "underlying_exchange", "option_type", "side", "expiry", "strike", "offset", "lots", "product"}
# Fields editable at any time, including after placement.
_LIVE_EDITABLE_FIELDS = {"sl_points", "targets", "trailing_mode"}


def modify_trade(
    user_id: int,
    trade_id: int,
    fields: dict[str, Any],
    auth_token: str | None = None,
    broker: str | None = None,
    config: dict | None = None,
) -> dict[str, Any]:
    """Modify a position before or after placement.

    * DRAFT  → any field (re-resolves option/futures and rebuilds the preview).
    * ACTIVE → only SL (``sl_points``), ``targets`` (pending ones), and
      ``trailing_mode`` (per-trade override). Strike/lots/side are locked once
      the order is live.
    """
    with session_scope() as db:
        t = db.get(FrTrade, trade_id)
        if t is None or t.user_id != user_id:
            raise FrError("Trade not found", 404)
        status = t.status
        is_draft = status == "draft"
        if status not in ("draft", "active"):
            raise FrError(f"Cannot modify a {status} trade", 409)

    # ---- Active trade: limited, in-place edits ----
    if not is_draft:
        illegal = (set(fields) & _DRAFT_ONLY_FIELDS)
        if illegal:
            raise FrError(f"Cannot change {', '.join(sorted(illegal))} after the order is placed", 409)
        with session_scope() as db:
            t = db.get(FrTrade, trade_id)
            changes: list[str] = []

            if "sl_points" in fields and fields["sl_points"] is not None:
                sl_points = float(fields["sl_points"])
                t.sl_points = sl_points
                t.sl_price = round(t.entry_futures_price - t.direction * sl_points, 2)
                t.sl_basis = "manual"
                changes.append(f"SL→{t.sl_price} ({sl_points} pts)")

            if "trailing_mode" in fields and fields["trailing_mode"]:
                meta = dict(t.meta or {})
                meta["trailing_mode"] = str(fields["trailing_mode"])
                t.meta = meta
                changes.append(f"trailing→{fields['trailing_mode']}")

            if "targets" in fields and fields["targets"] is not None:
                # Replace only the PENDING targets; keep already-hit ones intact.
                hit = db.execute(
                    select(FrTradeTarget).where(
                        FrTradeTarget.trade_id == trade_id, FrTradeTarget.status == "hit"
                    ).order_by(FrTradeTarget.seq)
                ).scalars().all()
                hit_lots = sum(int(r.exit_qty) for r in hit) // max(1, t.lot_size)
                remaining_lots = max(0, t.lots - hit_lots)
                base_seq = len(hit)
                template = [
                    {"seq": base_seq + i + 1, "points": float(x["points"]), "exit_pct": float(x.get("exit_pct", 0))}
                    for i, x in enumerate(fields["targets"])
                    if float(x.get("points", 0)) > 0
                ]
                new_rows = _build_targets(t.entry_futures_price, t.direction, remaining_lots, t.lot_size, template)
                db.execute(
                    text("DELETE FROM fr_trade_target WHERE trade_id = :tid AND status = 'pending'"),
                    {"tid": trade_id},
                )
                for tr in new_rows:
                    db.add(FrTradeTarget(
                        trade_id=trade_id, seq=tr["seq"], points=tr["points"], exit_pct=tr["exit_pct"],
                        trigger_price=tr["trigger_price"], exit_qty=tr["exit_qty"], status="pending",
                    ))
                changes.append(f"targets×{len(new_rows)}")

            if not changes:
                raise FrError("No editable fields provided", 400)
            t.modified_by = user_id
            log_event(
                db, trade_id=trade_id, user_id=user_id, kind="modified",
                message="Modified active trade: " + "; ".join(changes), payload={"fields": list(fields)},
            )
        return get_trade(user_id, trade_id) or {}

    # ---- Draft: merge params and fully re-resolve the preview ----
    with session_scope() as db:
        t = db.get(FrTrade, trade_id)
        p = dict((t.meta or {}).get("params") or {})
    p.update({k: v for k, v in fields.items() if v is not None})
    p = _normalise_params(p)
    if auth_token and broker:
        plan = _resolve_trade_plan(auth_token, broker, config, p, require_price=False)
    else:
        ctx = load_broker_context_sync(user_id)
        if ctx is None:
            raise FrError("No active broker session to re-resolve the draft", 403)
        plan = _resolve_trade_plan(ctx["auth_token"], ctx["broker"], ctx["config"], p, require_price=False)

    with session_scope() as db:
        t = db.get(FrTrade, trade_id)
        t.underlying = p["underlying"]
        t.option_symbol = plan["option_symbol"]
        t.option_exchange = plan["option_exchange"]
        t.option_type = p["option_type"]
        t.side = p["side"]
        t.product = p["product"]
        t.expiry = p["expiry"]
        t.strike = plan["strike_val"]
        t.lots = p["lots"]
        t.lot_size = plan["lot_size"]
        t.total_qty = plan["total_qty"]
        t.remaining_qty = plan["total_qty"]
        t.entry_option_price = plan["entry_opt"]
        t.futures_symbol = plan["fut_symbol"]
        t.futures_exchange = plan["fut_exchange"]
        t.entry_futures_price = plan["entry_fut"]
        t.direction = plan["direction"]
        t.sl_points = plan["sl_points"]
        t.sl_price = plan["sl_price"]
        t.modified_by = user_id
        meta = dict(t.meta or {})
        meta["params"] = p
        meta["offset"] = p["offset"] if p["strike"] is None else None
        t.meta = meta
        db.execute(text("DELETE FROM fr_trade_target WHERE trade_id = :tid"), {"tid": trade_id})
        _persist_targets(db, trade_id, plan["target_rows"])
        log_event(
            db, trade_id=trade_id, user_id=user_id, kind="modified",
            message=f"Draft updated: {p['side']} {p['lots']} lot(s) {plan['option_symbol']}",
            payload={"fields": list(fields)},
        )
    return get_trade(user_id, trade_id) or {}


def delete_trade(user_id: int, trade_id: int) -> bool:
    """Delete a draft (or an already-closed) trade. Active trades must be
    exited first — we never silently drop a live position."""
    with session_scope() as db:
        t = db.get(FrTrade, trade_id)
        if t is None or t.user_id != user_id:
            raise FrError("Trade not found", 404)
        if t.status == "active":
            raise FrError("Close the position before deleting it", 409)
        db.delete(t)  # FK cascade removes targets + events
    return True
