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

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

from backend.futures_risk import service as fr
from backend.futures_risk.service import FrError
from backend.services.trading_mode_service import get_trading_mode

logger = logging.getLogger(__name__)

router = APIRouter()

_DEDUP_TTL_SECONDS = 10.0
_dedup_lock = threading.Lock()
_recent_client_orders: dict[str, float] = {}


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


async def _resolve_api_user(request: Request) -> tuple[int, str, str, dict]:
    from backend.dependencies import get_api_user, get_db

    async for db in get_db():
        return await get_api_user(request, db)
    raise HTTPException(status_code=500, detail="Database session unavailable")


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
    options_exchange = "NFO"
    if selected and selected_expiry:
        try:
            strike_data = fr.list_strikes(selected, underlying_exchange, selected_expiry, "CE", auth_token, broker_name, config)
            strikes = strike_data.get("strikes") or []
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
    from backend.services.quotes_service import get_quotes_with_auth

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
    return {
        "symbol": symbol,
        "exchange": exchange,
        "ltp": ltp,
        "status": "success" if ok else "error",
        "message": response.get("message") if isinstance(response, dict) else None,
    }


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
        booked_pnl = 0.0
        open_pnl = 0.0
        active_count = 0
        for trade in fr.list_trades(user_id, status="all"):
            if str(trade.get("underlying", "")).upper() != payload.underlying.upper():
                continue
            booked_pnl += float(trade.get("realized_pnl") or 0)
            if trade.get("status") != "active":
                continue
            active_count += 1
            live_opt = quotes_by_symbol.get(trade.get("option_symbol"))
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
        user_id, auth_token, broker_name, config = await _resolve_api_user(request)
        body = await _request_json(request)
        payload = FuturesRiskQuickOrder.model_validate(body)
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
    mode = await _get_trading_mode()

    try:
        trade = fr.place_trade(
            user_id=user_id,
            mode=mode,
            auth_token=auth_token,
            broker=broker_name,
            config=config,
            params=params,
        )
    except FrError as exc:
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
        return JSONResponse(
            content={"status": "error", "message": message, "data": trade},
            status_code=200,
        )

    return JSONResponse(
        content={"status": "success", "message": "Quick order placed", "data": trade},
        status_code=200,
    )


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
