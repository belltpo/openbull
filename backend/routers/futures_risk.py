"""
Futures-Risk Options web API (/web/fr/*).

* Admin: target template, stop-loss/trailing config, and underlying→futures
  symbol-map CRUD.
* User: place option trades (Buy/Sell CE/PE) with futures-based risk, and view
  the live dashboard (trades, targets, auto-exit logs).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import BrokerContext, get_broker_context, get_current_user, get_db
from backend.futures_risk import service as fr
from backend.futures_risk.service import FrError
from backend.models.user import User
from backend.services.trading_mode_service import get_trading_mode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/web/fr", tags=["futures-risk"])


def _require_admin(user: User) -> None:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class ConfigUpdate(BaseModel):
    key: str = Field(..., min_length=1, max_length=100)
    value: str = Field(..., max_length=500)


@router.get("/config")
async def get_config(user: User = Depends(get_current_user)):
    return {"status": "success", "data": fr.get_config_map()}


@router.post("/config")
async def update_config(payload: ConfigUpdate, user: User = Depends(get_current_user)):
    _require_admin(user)
    if not fr.set_config(payload.key, payload.value):
        raise HTTPException(status_code=400, detail="Unknown or non-editable config key")
    return {"status": "success", "key": payload.key, "value": payload.value}


# ---------------------------------------------------------------------------
# Target template
# ---------------------------------------------------------------------------

class TargetCreate(BaseModel):
    points: float = Field(..., gt=0)
    exit_pct: float = Field(..., ge=0, le=100)
    enabled: bool = True


class TargetUpdate(BaseModel):
    points: float | None = Field(None, gt=0)
    exit_pct: float | None = Field(None, ge=0, le=100)
    enabled: bool | None = None


@router.get("/targets")
async def get_targets(user: User = Depends(get_current_user)):
    return {"status": "success", "data": fr.list_targets()}


@router.post("/targets")
async def add_target(payload: TargetCreate, user: User = Depends(get_current_user)):
    _require_admin(user)
    return {"status": "success", "data": fr.create_target(payload.points, payload.exit_pct, payload.enabled)}


@router.put("/targets/{target_id}")
async def edit_target(target_id: int, payload: TargetUpdate, user: User = Depends(get_current_user)):
    _require_admin(user)
    fields = payload.model_dump(exclude_none=True)
    result = fr.update_target(target_id, fields)
    if result is None:
        raise HTTPException(status_code=404, detail="Target not found")
    return {"status": "success", "data": result}


@router.delete("/targets/{target_id}")
async def remove_target(target_id: int, user: User = Depends(get_current_user)):
    _require_admin(user)
    if not fr.delete_target(target_id):
        raise HTTPException(status_code=404, detail="Target not found")
    return {"status": "success"}


# ---------------------------------------------------------------------------
# Symbol map
# ---------------------------------------------------------------------------

class SymbolMapCreate(BaseModel):
    underlying: str = Field(..., min_length=1, max_length=50)
    underlying_exchange: str = "NSE_INDEX"
    futures_symbol: str | None = None
    futures_exchange: str = "NFO"
    lot_size: int = 0
    auto_resolve: bool = True
    enabled: bool = True


class SymbolMapUpdate(BaseModel):
    underlying: str | None = None
    underlying_exchange: str | None = None
    futures_symbol: str | None = None
    futures_exchange: str | None = None
    lot_size: int | None = None
    auto_resolve: bool | None = None
    enabled: bool | None = None


@router.get("/symbol-maps")
async def get_symbol_maps(user: User = Depends(get_current_user)):
    return {"status": "success", "data": fr.list_symbol_maps()}


@router.post("/symbol-maps")
async def add_symbol_map(payload: SymbolMapCreate, user: User = Depends(get_current_user)):
    _require_admin(user)
    try:
        return {"status": "success", "data": fr.create_symbol_map(payload.model_dump())}
    except FrError as e:
        raise HTTPException(status_code=e.status, detail=e.message)


@router.put("/symbol-maps/{map_id}")
async def edit_symbol_map(map_id: int, payload: SymbolMapUpdate, user: User = Depends(get_current_user)):
    _require_admin(user)
    result = fr.update_symbol_map(map_id, payload.model_dump(exclude_none=True))
    if result is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return {"status": "success", "data": result}


@router.delete("/symbol-maps/{map_id}")
async def remove_symbol_map(map_id: int, user: User = Depends(get_current_user)):
    _require_admin(user)
    if not fr.delete_symbol_map(map_id):
        raise HTTPException(status_code=404, detail="Mapping not found")
    return {"status": "success"}


# ---------------------------------------------------------------------------
# Resolution helpers (for the order popup)
# ---------------------------------------------------------------------------

@router.get("/resolve-futures")
async def resolve_futures(underlying: str, user: User = Depends(get_current_user)):
    fut = fr.resolve_futures(underlying)
    if fut is None:
        raise HTTPException(status_code=404, detail=f"No futures mapping for {underlying}")
    return {"status": "success", "data": fut}


@router.get("/expiries")
async def expiries(
    underlying: str,
    exchange: str = "NSE_INDEX",
    user: User = Depends(get_current_user),
):
    return {"status": "success", "data": fr.list_expiries(underlying, exchange)}


@router.get("/strikes")
async def strikes(
    underlying: str,
    expiry: str,
    option_type: str,
    exchange: str = "NSE_INDEX",
    ctx: BrokerContext = Depends(get_broker_context),
):
    data = fr.list_strikes(
        underlying, exchange, expiry, option_type,
        ctx.auth_token, ctx.broker_name, ctx.broker_config,
    )
    return {"status": "success", "data": data}


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------

class TargetOverride(BaseModel):
    points: float = Field(..., gt=0)
    exit_pct: float = Field(0, ge=0, le=100)


class PlaceTrade(BaseModel):
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
    targets: list[TargetOverride] | None = None


@router.post("/trade")
async def place_trade(
    payload: PlaceTrade,
    ctx: BrokerContext = Depends(get_broker_context),
    db: AsyncSession = Depends(get_db),
):
    mode = await get_trading_mode(db)
    try:
        trade = fr.place_trade(
            user_id=ctx.user.id,
            mode=mode,
            auth_token=ctx.auth_token,
            broker=ctx.broker_name,
            config=ctx.broker_config,
            params=payload.model_dump(),
        )
    except FrError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    return {"status": "success", "data": trade}


@router.get("/trades")
async def list_trades(status: str = "all", user: User = Depends(get_current_user)):
    return {"status": "success", "data": fr.list_trades(user.id, status)}


@router.get("/trades/{trade_id}")
async def get_trade(trade_id: int, user: User = Depends(get_current_user)):
    trade = fr.get_trade(user.id, trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")
    return {"status": "success", "data": trade}


@router.post("/trades/{trade_id}/exit")
async def exit_trade(trade_id: int, user: User = Depends(get_current_user)):
    try:
        trade = fr.manual_exit(user.id, trade_id)
    except FrError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    return {"status": "success", "data": trade}
