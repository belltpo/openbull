"""
External API endpoints for Futures-Risk quick orders.

This module is intended for non-browser clients such as NinjaTrader. It uses
API-key auth and delegates order creation to the same Futures-Risk service used
by the OpenBull quick-order popup.
"""

from __future__ import annotations

import logging
import json
import threading
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

from backend.futures_risk import service as fr
from backend.futures_risk.service import FrError
from backend.services.trading_mode_service import get_trading_mode

logger = logging.getLogger(__name__)

router = APIRouter()

_DEDUP_TTL_SECONDS = 10.0
_QUOTE_CACHE_TTL_SECONDS = 3.0
_dedup_lock = threading.Lock()
_quote_cache_lock = threading.Lock()
_recent_client_orders: dict[str, float] = {}
_recent_quotes: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}


class QuickOrderTarget(BaseModel):
    points: float = Field(..., gt=0)
    exit_pct: float = Field(0, ge=0, le=100)


class FuturesRiskQuickOrder(BaseModel):
    apikey: str | None = None
    client_order_id: str | None = Field(None, max_length=100)
    source: str | None = Field("ninjatrader", max_length=50)
    underlying: str = Field(..., min_length=1)
    underlying_exchange: str = "NSE_INDEX"
    expiry: str = Field(..., min_length=1)
    option_type: str = Field(..., pattern="^(CE|PE)$")
    side: str = Field(..., pattern="^(BUY|SELL)$")
    product: str | None = None
    lots: int = Field(..., ge=1)
    strike: float | None = None
    offset: str | None = "ATM"
    sl_points: float | None = None
    targets: list[QuickOrderTarget] | None = None
    target_template_id: int | None = None


class FuturesRiskQuickOrderPreview(BaseModel):
    apikey: str | None = None
    underlying: str = Field(..., min_length=1)
    underlying_exchange: str = "NSE_INDEX"
    expiry: str = Field(..., min_length=1)
    ce_strike: float | None = None
    pe_strike: float | None = None


class FuturesRiskQuickOrderOptions(BaseModel):
    apikey: str | None = None
    underlying: str | None = None
    underlying_exchange: str | None = None
    expiry: str | None = None


class FuturesRiskQuickOrderSettings(BaseModel):
    apikey: str | None = None
    underlying: str = Field(..., min_length=1)
    underlying_exchange: str | None = None
    expiry: str | None = None
    ce_strike: float | None = None
    pe_strike: float | None = None
    lots: int = Field(..., ge=1)
    sl_points: float = Field(..., gt=0)
    product: str | None = "NRML"
    target_template_id: int | None = None


class FuturesRiskLevelTarget(BaseModel):
    seq: int | None = Field(None, ge=1)
    price: float = Field(..., gt=0)
    exit_pct: float | None = Field(None, ge=0, le=100)


class FuturesRiskTradeLevels(BaseModel):
    apikey: str | None = None
    sl_price: float | None = Field(None, gt=0)
    targets: list[FuturesRiskLevelTarget] | None = None


async def _resolve_api_user(request: Request) -> tuple[int, str, str, dict]:
    from backend.dependencies import get_api_user, get_db

    async for db in get_db():
        return await get_api_user(request, db)
    raise HTTPException(status_code=500, detail="Database session unavailable")


async def _resolve_api_identity(request: Request) -> int:
    from backend.dependencies import get_api_user_id, get_db

    async for db in get_db():
        return await get_api_user_id(request, db)
    raise HTTPException(status_code=500, detail="Database session unavailable")


async def _resolve_api_user_for_mode(request: Request, mode: str) -> tuple[int, str, str, dict]:
    if mode != "sandbox":
        return await _resolve_api_user(request)
    try:
        return await _resolve_api_user(request)
    except HTTPException as exc:
        if exc.status_code not in (401, 403):
            raise
        user_id = await _resolve_api_identity(request)
        logger.info("Using API-key identity without broker context for sandbox quick-order user_id=%s", user_id)
        return user_id, "", "sandbox", {}


async def _get_trading_mode() -> str:
    from backend.dependencies import get_db

    async for db in get_db():
        return await get_trading_mode(db)
    return await get_trading_mode()


async def _request_json(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}


def _remember_client_order(client_order_id: str | None) -> bool:
    """Return False when the client id was seen recently."""
    if not client_order_id:
        return True
    now = time.monotonic()
    with _dedup_lock:
        expired = [key for key, expires_at in _recent_client_orders.items() if expires_at <= now]
        for key in expired:
            _recent_client_orders.pop(key, None)
        if client_order_id in _recent_client_orders:
            return False
        _recent_client_orders[client_order_id] = now + _DEDUP_TTL_SECONDS
    return True


def _contract_templates() -> dict[str, Any]:
    raw = fr.get_config_map().get("contract_order_templates", {}).get("value") or "{}"
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _save_contract_templates(data: dict[str, Any]) -> None:
    if not fr.set_config("contract_order_templates", json.dumps(data)):
        raise FrError("Unable to save contract quick-order settings", 500)


@router.post("/futures-risk/quick-order/options")
async def api_futures_risk_quick_order_options(request: Request):
    """Return dropdown data and saved per-contract quick-order settings."""
    try:
        _user_id, auth_token, broker_name, config = await _resolve_api_user(request)
        body = await _request_json(request)
        payload = FuturesRiskQuickOrderOptions.model_validate(body)
    except ValidationError as exc:
        return JSONResponse(
            content={"status": "error", "message": exc.errors()[0].get("msg", "Invalid request")},
            status_code=422,
        )
    except Exception as exc:
        return _error_response(exc)

    maps = [m for m in fr.list_symbol_maps() if m.get("enabled")]
    underlyings = [str(m["underlying"]) for m in maps]
    selected = (payload.underlying or (underlyings[0] if underlyings else "")).upper()
    selected_map = next((m for m in maps if str(m.get("underlying", "")).upper() == selected), None)
    underlying_exchange = str((selected_map or {}).get("underlying_exchange") or payload.underlying_exchange or "NSE_INDEX")
    expiries = fr.list_expiries(selected, underlying_exchange) if selected else []
    selected_expiry = payload.expiry or (expiries[0]["value"] if expiries else "")
    strikes: list[float] = []
    atm: float | None = None
    open_atm: float | None = None
    ce_default_strike: float | None = None
    pe_default_strike: float | None = None
    options_exchange = "NFO"
    if selected and selected_expiry:
        try:
            strike_data = fr.list_strikes(selected, underlying_exchange, selected_expiry, "CE", auth_token, broker_name, config)
            strikes = strike_data.get("strikes") or []
            atm = strike_data.get("atm")
            open_atm = strike_data.get("open_atm")
            ce_default_strike = strike_data.get("ce_default_strike")
            pe_default_strike = strike_data.get("pe_default_strike")
            options_exchange = strike_data.get("options_exchange") or options_exchange
        except Exception:
            logger.debug("NT quick-order strike lookup failed", exc_info=True)

    templates = [
        {"id": t["id"], "name": t["name"], "is_default": t.get("is_default", False)}
        for t in fr.list_target_templates(enabled_only=True)
    ]
    saved = _contract_templates().get(selected) if selected else None
    config_map = fr.get_config_map()
    defaults = {
        "underlying_exchange": underlying_exchange,
        "expiry": saved.get("expiry") if isinstance(saved, dict) else selected_expiry,
        "ce_strike": saved.get("ce_strike") if isinstance(saved, dict) else None,
        "pe_strike": saved.get("pe_strike") if isinstance(saved, dict) else None,
        "lots": saved.get("lots") if isinstance(saved, dict) else config_map.get("default_lots", {}).get("value", "1"),
        "sl_points": saved.get("sl_points") if isinstance(saved, dict) else config_map.get("default_sl_points", {}).get("value", "5"),
        "product": saved.get("product") if isinstance(saved, dict) else config_map.get("default_product", {}).get("value", "NRML"),
        "target_template_id": saved.get("target_template_id") if isinstance(saved, dict) else None,
    }
    return JSONResponse(
        content={
            "status": "success",
            "data": {
                "mode": await _get_trading_mode(),
                "underlyings": underlyings,
                "underlying_exchange": underlying_exchange,
                "expiries": expiries,
                "strikes": strikes,
                "atm": atm,
                "open_atm": open_atm,
                "ce_default_strike": ce_default_strike,
                "pe_default_strike": pe_default_strike,
                "options_exchange": options_exchange,
                "templates": templates,
                "saved": defaults,
            },
        },
        status_code=200,
    )


@router.post("/futures-risk/quick-order/settings")
async def api_futures_risk_quick_order_settings(request: Request):
    """Create/update saved quick-order defaults for one contract."""
    try:
        await _resolve_api_user(request)
        body = await _request_json(request)
        payload = FuturesRiskQuickOrderSettings.model_validate(body)
    except ValidationError as exc:
        return JSONResponse(
            content={"status": "error", "message": exc.errors()[0].get("msg", "Invalid request")},
            status_code=422,
        )
    except Exception as exc:
        return _error_response(exc)

    data = _contract_templates()
    data[payload.underlying.upper()] = {
        "underlying_exchange": (payload.underlying_exchange or "").upper(),
        "expiry": (payload.expiry or "").upper(),
        "ce_strike": payload.ce_strike,
        "pe_strike": payload.pe_strike,
        "lots": str(payload.lots),
        "sl_points": str(payload.sl_points),
        "product": (payload.product or "NRML").upper(),
        "target_template_id": payload.target_template_id,
    }
    _save_contract_templates(data)
    return JSONResponse(content={"status": "success", "data": data[payload.underlying.upper()]}, status_code=200)


@router.post("/futures-risk/quick-order/settings/delete")
async def api_futures_risk_quick_order_settings_delete(request: Request):
    """Delete saved quick-order defaults for one contract."""
    try:
        await _resolve_api_user(request)
        body = await _request_json(request)
        underlying = str(body.get("underlying", "")).strip().upper()
    except Exception as exc:
        return _error_response(exc)
    if not underlying:
        return JSONResponse(content={"status": "error", "message": "underlying is required"}, status_code=400)
    data = _contract_templates()
    data.pop(underlying, None)
    _save_contract_templates(data)
    return JSONResponse(content={"status": "success"}, status_code=200)


def _quote_payload(symbol: str, exchange: str, auth_token: str, broker_name: str, config: dict) -> dict[str, Any]:
    from backend.services.market_data_cache import get_market_data_cache
    from backend.services.market_data_cache import process_market_data
    from backend.services.quotes_service import get_quotes_with_auth

    key = (str(symbol).upper(), str(exchange).upper())
    now = time.monotonic()

    def fresh_cached_ltp() -> float | None:
        try:
            entry = get_market_data_cache().get_all(symbol, exchange)
            last_update = float(entry.get("last_update") or 0)
            ltp_value = (entry.get("ltp") or {}).get("value")
            ltp = float(ltp_value or 0)
        except Exception:
            return None
        if ltp <= 0 or last_update <= 0:
            return None
        if time.time() - last_update > _QUOTE_CACHE_TTL_SECONDS:
            return None
        return ltp

    def remember_ltp(value: float) -> None:
        if value <= 0:
            return
        try:
            process_market_data({
                "symbol": symbol,
                "exchange": exchange,
                "mode": 1,
                "data": {"ltp": value, "timestamp": time.time(), "volume": 0},
            })
        except Exception:
            logger.debug("Unable to seed market-data cache for %s/%s", symbol, exchange, exc_info=True)

    try:
        cached_ltp = fresh_cached_ltp()
        if cached_ltp and cached_ltp > 0:
            payload = {
                "symbol": symbol,
                "exchange": exchange,
                "ltp": cached_ltp,
                "status": "success",
                "source": "websocket_cache",
                "message": None,
            }
            with _quote_cache_lock:
                _recent_quotes[key] = (now + _QUOTE_CACHE_TTL_SECONDS, payload)
            return payload
    except Exception:
        pass

    with _quote_cache_lock:
        cached = _recent_quotes.get(key)
        if cached and cached[0] > now:
            return dict(cached[1])

    ok, response, _ = get_quotes_with_auth(
        symbol=symbol,
        exchange=exchange,
        auth_token=auth_token,
        broker=broker_name,
        config=config,
    )
    data = response.get("data", {}) if ok and isinstance(response, dict) else {}
    try:
        ltp = float(data.get("ltp") or 0)
    except (TypeError, ValueError):
        ltp = 0.0
    remember_ltp(ltp)
    payload = {
        "symbol": symbol,
        "exchange": exchange,
        "ltp": ltp,
        "status": "success" if ok else "error",
        "source": "rest",
        "message": response.get("message") if isinstance(response, dict) else None,
    }
    with _quote_cache_lock:
        _recent_quotes[key] = (now + _QUOTE_CACHE_TTL_SECONDS, payload)
    return payload


@router.post("/futures-risk/quick-order/preview")
async def api_futures_risk_quick_order_preview(request: Request):
    """Resolve the current quick-order symbols and return live quote snapshots."""
    try:
        user_id, auth_token, broker_name, config = await _resolve_api_user(request)
        body = await _request_json(request)
        payload = FuturesRiskQuickOrderPreview.model_validate(body)
    except ValidationError as exc:
        return JSONResponse(
            content={"status": "error", "message": exc.errors()[0].get("msg", "Invalid request")},
            status_code=422,
        )
    except Exception as exc:
        return _error_response(exc)

    try:
        mode = await _get_trading_mode()
        maps = [m for m in fr.list_symbol_maps() if m.get("enabled")]
        selected_map = next(
            (m for m in maps if str(m.get("underlying", "")).upper() == payload.underlying.upper()),
            None,
        )
        underlying_exchange = str((selected_map or {}).get("underlying_exchange") or payload.underlying_exchange)
        fut = fr.resolve_futures(payload.underlying)
        if fut is None:
            return JSONResponse(
                content={"status": "error", "message": f"No futures mapping configured for {payload.underlying}"},
                status_code=404,
            )

        data: dict[str, Any] = {
            "mode": mode,
            "futures": _quote_payload(fut["symbol"], fut["exchange"], auth_token, broker_name, config),
            "ce": None,
            "pe": None,
        }
        if payload.ce_strike:
            ce = fr._resolve_option(  # type: ignore[attr-defined]
                payload.underlying,
                underlying_exchange,
                payload.expiry,
                "CE",
                "BUY",
                payload.ce_strike,
                "ATM",
                auth_token,
                broker_name,
                config,
            )
            data["ce"] = _quote_payload(ce["symbol"], ce["exchange"], auth_token, broker_name, config)
        if payload.pe_strike:
            pe = fr._resolve_option(  # type: ignore[attr-defined]
                payload.underlying,
                underlying_exchange,
                payload.expiry,
                "PE",
                "BUY",
                payload.pe_strike,
                "ATM",
                auth_token,
                broker_name,
                config,
            )
            data["pe"] = _quote_payload(pe["symbol"], pe["exchange"], auth_token, broker_name, config)
        quotes_by_symbol = {
            (data["ce"] or {}).get("symbol"): (data["ce"] or {}).get("ltp"),
            (data["pe"] or {}).get("symbol"): (data["pe"] or {}).get("ltp"),
        }
        session_suffix = ":" + fr._session_date_ist()  # type: ignore[attr-defined]
        booked_pnl = 0.0
        open_pnl = 0.0
        active_count = 0
        for trade in fr.list_trades(user_id, status="all"):
            if str(trade.get("underlying", "")).upper() != payload.underlying.upper():
                continue
            if int(trade.get("phase_no") or 0) <= 0:
                continue
            if not str(trade.get("phase_group") or "").endswith(session_suffix):
                continue
            booked_pnl += float(trade.get("realized_pnl") or 0)
            if trade.get("status") != "active":
                continue
            active_count += 1
            live_opt = quotes_by_symbol.get(trade.get("option_symbol"))
            if live_opt is None:
                option_symbol = trade.get("option_symbol")
                option_exchange = trade.get("option_exchange")
                if not option_symbol or not option_exchange:
                    continue
                quote = _quote_payload(
                    option_symbol,
                    option_exchange,
                    auth_token,
                    broker_name,
                    config,
                )
                live_opt = quote.get("ltp") if quote.get("status") == "success" else None
                quotes_by_symbol[option_symbol] = live_opt
            if live_opt is None:
                continue
            entry_opt = float(trade.get("entry_option_price") or 0)
            remaining_qty = int(trade.get("remaining_qty") or 0)
            direction = 1 if trade.get("side") == "BUY" else -1
            open_pnl += (float(live_opt) - entry_opt) * remaining_qty * direction
        data["mtm"] = {
            "booked": round(booked_pnl, 2),
            "open": round(open_pnl, 2),
            "total": round(booked_pnl + open_pnl, 2),
            "active_count": active_count,
        }
    except FrError as exc:
        return JSONResponse(content={"status": "error", "message": exc.message}, status_code=exc.status)
    except Exception:
        logger.exception("Unexpected error in Futures-Risk quick-order preview API")
        return JSONResponse(
            content={"status": "error", "message": "An unexpected error occurred"},
            status_code=500,
        )

    return JSONResponse(content={"status": "success", "data": data}, status_code=200)


@router.post("/futures-risk/quick-order")
async def api_futures_risk_quick_order(request: Request):
    """Place a Futures-Risk option quick order via API key.

    External clients must send an API key either as ``apikey`` in the JSON body
    or as ``X-API-KEY``. The order is still executed by OpenBull, so existing
    Futures-Risk phase, target, stop-loss, trailing, sandbox/live mode, and
    broker rejection handling stay in one place.
    """
    try:
        body = await _request_json(request)
        payload = FuturesRiskQuickOrder.model_validate(body)
        mode = await _get_trading_mode()
        user_id, auth_token, broker_name, config = await _resolve_api_user_for_mode(request, mode)
    except ValidationError as exc:
        return JSONResponse(
            content={"status": "error", "message": exc.errors()[0].get("msg", "Invalid request")},
            status_code=422,
        )
    except Exception as exc:
        return _error_response(exc)

    if not _remember_client_order(payload.client_order_id):
        return JSONResponse(
            content={"status": "error", "message": "Duplicate quick-order request ignored"},
            status_code=409,
        )

    params = payload.model_dump(exclude={"apikey", "client_order_id", "source"})

    try:
        trade = fr.place_trade(
            user_id=user_id,
            mode=mode,
            auth_token=auth_token,
            broker=broker_name,
            config=config,
            params=params,
        )
        logger.info(
            "Futures-Risk API quick-order result source=%s mode=%s broker=%s underlying=%s status=%s trade_id=%s entry_order_id=%s message=%s",
            payload.source,
            mode,
            broker_name,
            payload.underlying,
            trade.get("status"),
            trade.get("id"),
            trade.get("entry_order_id"),
            trade.get("message"),
        )
    except FrError as exc:
        logger.warning(
            "Futures-Risk API quick-order rejected source=%s mode=%s underlying=%s message=%s",
            payload.source,
            mode,
            payload.underlying,
            exc.message,
        )
        return JSONResponse(
            content={"status": "error", "message": exc.message},
            status_code=exc.status,
        )
    except Exception:
        logger.exception("Unexpected error in Futures-Risk quick-order API")
        return JSONResponse(
            content={"status": "error", "message": "An unexpected error occurred"},
            status_code=500,
        )

    if trade.get("status") == "error":
        message = "Broker rejected the entry order"
        for event in trade.get("events") or []:
            if event.get("severity") == "error":
                message = event.get("message") or message
                break
        logger.warning(
            "Futures-Risk API quick-order returned broker issue source=%s mode=%s underlying=%s trade_id=%s message=%s",
            payload.source,
            mode,
            payload.underlying,
            trade.get("id"),
            message,
        )
        return JSONResponse(
            content={"status": "error", "message": message, "data": trade},
            status_code=200,
        )

    return JSONResponse(
        content={"status": "success", "message": "Quick order placed", "data": trade},
        status_code=200,
    )


@router.get("/futures-risk/trades/{trade_id}")
async def api_futures_risk_trade_detail(trade_id: int, request: Request):
    """Return one Futures-Risk trade for API-key clients."""
    try:
        user_id = await _resolve_api_identity(request)
    except Exception as exc:
        return _error_response(exc)

    trade = fr.get_trade(user_id, trade_id)
    if trade is None:
        return JSONResponse(content={"status": "error", "message": "Trade not found"}, status_code=404)
    return JSONResponse(content={"status": "success", "data": trade}, status_code=200)


@router.get("/futures-risk/trades")
async def api_futures_risk_trade_list(
    request: Request,
    underlying: str | None = Query(None),
    status: str = Query("all"),
    current_session: bool = Query(True),
):
    """Return Futures-Risk trades for API-key clients.

    NinjaTrader uses this to restore one Bell drawing per phase after chart or
    workspace reload. By default it returns the selected instrument's current
    trading-session phases, which matches the Futures-Risk day-wise phase logic.
    """
    try:
        user_id = await _resolve_api_identity(request)
    except Exception as exc:
        return _error_response(exc)

    normalized_underlying = (underlying or "").strip().upper()
    session_suffix = ":" + fr._session_date_ist() if current_session else ""  # type: ignore[attr-defined]
    trades = []
    for trade in fr.list_trades(user_id, status=status):
        if normalized_underlying and str(trade.get("underlying") or "").upper() != normalized_underlying:
            continue
        if current_session and not str(trade.get("phase_group") or "").endswith(session_suffix):
            continue
        if int(trade.get("phase_no") or 0) <= 0:
            continue
        trades.append(trade)
    trades.sort(key=lambda t: (str(t.get("underlying") or ""), int(t.get("phase_no") or 0), int(t.get("id") or 0)))
    return JSONResponse(content={"status": "success", "data": trades}, status_code=200)


@router.put("/futures-risk/trades/{trade_id}/levels")
async def api_futures_risk_trade_levels(trade_id: int, request: Request):
    """Update active trade SL/target levels from chart-dragged futures prices.

    NT drawing tools work in absolute futures prices. OpenBull stores live
    edits as SL/target point distances from the immutable filled futures entry,
    so this endpoint performs that conversion and then delegates to the shared
    Futures-Risk modify service.
    """
    try:
        user_id, auth_token, broker_name, config = await _resolve_api_user(request)
        body = await _request_json(request)
        payload = FuturesRiskTradeLevels.model_validate(body)
    except ValidationError as exc:
        return JSONResponse(
            content={"status": "error", "message": exc.errors()[0].get("msg", "Invalid request")},
            status_code=422,
        )
    except Exception as exc:
        return _error_response(exc)

    trade = fr.get_trade(user_id, trade_id)
    if trade is None:
        return JSONResponse(content={"status": "error", "message": "Trade not found"}, status_code=404)

    try:
        entry = float(trade.get("entry_futures_price") or 0)
        direction = int(trade.get("direction") or 0)
    except (TypeError, ValueError):
        entry, direction = 0.0, 0
    if entry <= 0 or direction not in (-1, 1):
        return JSONResponse(
            content={"status": "error", "message": "Trade entry/direction is not available for level sync"},
            status_code=409,
        )

    fields: dict[str, Any] = {}
    if payload.sl_price is not None:
        sl_points = round((entry - float(payload.sl_price)) * direction, 2)
        if sl_points <= 0:
            return JSONResponse(
                content={"status": "error", "message": "SL must remain on the risk side of entry"},
                status_code=400,
            )
        fields["sl_points"] = sl_points

    if payload.targets is not None:
        existing_by_seq = {
            int(t.get("seq")): t
            for t in (trade.get("targets") or [])
            if t.get("seq") is not None
        }
        active_targets: list[dict[str, Any]] = []
        for idx, target in enumerate(payload.targets, start=1):
            seq = int(target.seq or idx)
            target_points = round((float(target.price) - entry) * direction, 2)
            if target_points <= 0:
                return JSONResponse(
                    content={"status": "error", "message": f"Target {seq} must remain on the profit side of entry"},
                    status_code=400,
                )
            existing = existing_by_seq.get(seq, {})
            if str(existing.get("status") or "pending").lower() != "pending":
                return JSONResponse(
                    content={"status": "error", "message": f"Target {seq} is already {existing.get('status')} and cannot be edited"},
                    status_code=409,
                )
            active_targets.append(
                {
                    "points": target_points,
                    "exit_pct": float(target.exit_pct if target.exit_pct is not None else existing.get("exit_pct") or 0),
                }
            )
        fields["targets"] = active_targets

    if not fields:
        return JSONResponse(content={"status": "error", "message": "No level changes provided"}, status_code=400)

    try:
        updated = fr.modify_trade(
            user_id,
            trade_id,
            fields,
            auth_token=auth_token,
            broker=broker_name,
            config=config,
        )
    except FrError as exc:
        return JSONResponse(content={"status": "error", "message": exc.message}, status_code=exc.status)
    except Exception:
        logger.exception("Unexpected error in Futures-Risk level sync API")
        return JSONResponse(content={"status": "error", "message": "An unexpected error occurred"}, status_code=500)

    return JSONResponse(content={"status": "success", "message": "Trade levels updated", "data": updated}, status_code=200)


def _error_response(exc: Exception) -> JSONResponse:
    if isinstance(exc, HTTPException):
        message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(
            content={"status": "error", "message": message},
            status_code=exc.status_code,
        )
    logger.exception("Unexpected error in Futures-Risk API endpoint")
    return JSONResponse(
        content={"status": "error", "message": "An unexpected error occurred"},
        status_code=500,
    )
