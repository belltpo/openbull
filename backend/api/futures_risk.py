"""
External API endpoints for Futures-Risk quick orders.

This module is intended for non-browser clients such as NinjaTrader. It uses
API-key auth and delegates order creation to the same Futures-Risk service used
by the OpenBull quick-order popup.
"""

from __future__ import annotations

import logging
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
