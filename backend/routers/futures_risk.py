"""
Futures-Risk Options web API (/web/fr/*).

* Admin: target template, stop-loss/trailing config, and underlying→futures
  symbol-map CRUD.
* User: place option trades (Buy/Sell CE/PE) with futures-based risk, and view
  the live dashboard (trades, targets, auto-exit logs).
"""

from __future__ import annotations

import logging
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from backend.api.futures_risk import _broker_quote_error, _quote_key, _quote_payloads
from backend.dependencies import BrokerContext, get_broker_context, get_current_user, get_db
from backend.futures_risk import service as fr
from backend.futures_risk.strike_selection import normalize_method, normalize_moneyness
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
    value: str = Field(..., max_length=20000)


class ContractQuickOrderSettings(BaseModel):
    underlying: str = Field(..., min_length=1)
    underlying_exchange: str | None = None
    expiry: str | None = None
    ce_strike: float | None = None
    pe_strike: float | None = None
    strike_selection_method: str | None = None
    moneyness_selection: str | None = None
    lots: int = Field(..., ge=1)
    sl_points: float = Field(..., gt=0)
    product: str | None = "NRML"
    target_template_id: int | None = None


@router.get("/config")
async def get_config(user: User = Depends(get_current_user)):
    return {"status": "success", "data": await run_in_threadpool(fr.get_config_map)}


@router.post("/config")
async def update_config(payload: ConfigUpdate, user: User = Depends(get_current_user)):
    _require_admin(user)
    if not fr.set_config(payload.key, payload.value):
        raise HTTPException(status_code=400, detail="Unknown or non-editable config key")
    return {"status": "success", "key": payload.key, "value": payload.value}


@router.post("/quick-order/settings")
async def save_quick_order_settings(payload: ContractQuickOrderSettings, user: User = Depends(get_current_user)):
    """Save per-contract quick-order settings for the browser Quick Card."""
    raw = fr.get_config_map().get("contract_order_templates", {}).get("value") or "{}"
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    key = payload.underlying.strip().upper()
    data[key] = {
        "underlying_exchange": (payload.underlying_exchange or "").upper(),
        "expiry": (payload.expiry or "").upper(),
        "ce_strike": payload.ce_strike,
        "pe_strike": payload.pe_strike,
        "strike_selection_method": normalize_method(payload.strike_selection_method).value,
        "moneyness_selection": normalize_moneyness(payload.moneyness_selection).value,
        "lots": str(payload.lots),
        "sl_points": str(payload.sl_points),
        "product": (payload.product or "NRML").upper(),
        "target_template_id": payload.target_template_id,
    }
    if not fr.set_config("contract_order_templates", json.dumps(data, separators=(",", ":"))):
        raise HTTPException(status_code=500, detail="Unable to save contract quick-order settings")
    return {"status": "success", "data": {"underlying": key, **data[key]}}


# ---------------------------------------------------------------------------
# Target template
# ---------------------------------------------------------------------------

class TargetCreate(BaseModel):
    points: float = Field(..., gt=0)
    exit_pct: float = Field(..., ge=0, le=100)
    enabled: bool = True
    template_id: int | None = None


class TargetUpdate(BaseModel):
    points: float | None = Field(None, gt=0)
    exit_pct: float | None = Field(None, ge=0, le=100)
    enabled: bool | None = None


class TargetTemplateTarget(BaseModel):
    points: float = Field(..., gt=0)
    exit_pct: float = Field(0, ge=0, le=100)
    enabled: bool = True


class TargetTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    enabled: bool = True
    is_default: bool = False
    targets: list[TargetTemplateTarget] = Field(default_factory=list)


class TargetTemplateUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    enabled: bool | None = None
    is_default: bool | None = None
    targets: list[TargetTemplateTarget] | None = None


@router.get("/target-templates")
async def get_target_templates(user: User = Depends(get_current_user)):
    return {"status": "success", "data": await run_in_threadpool(fr.list_target_templates)}


@router.post("/target-templates")
async def add_target_template(payload: TargetTemplateCreate, user: User = Depends(get_current_user)):
    _require_admin(user)
    try:
        return {"status": "success", "data": fr.create_target_template(payload.model_dump())}
    except FrError as e:
        raise HTTPException(status_code=e.status, detail=e.message)


@router.put("/target-templates/{template_id}")
async def edit_target_template(template_id: int, payload: TargetTemplateUpdate, user: User = Depends(get_current_user)):
    _require_admin(user)
    try:
        result = fr.update_target_template(template_id, payload.model_dump(exclude_none=True))
    except FrError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    if result is None:
        raise HTTPException(status_code=404, detail="Target template not found")
    return {"status": "success", "data": result}


@router.delete("/target-templates/{template_id}")
async def remove_target_template(template_id: int, user: User = Depends(get_current_user)):
    _require_admin(user)
    try:
        if not fr.delete_target_template(template_id):
            raise HTTPException(status_code=404, detail="Target template not found")
    except FrError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    return {"status": "success"}


@router.get("/targets")
async def get_targets(template_id: int | None = None, user: User = Depends(get_current_user)):
    return {"status": "success", "data": await run_in_threadpool(fr.list_targets, template_id=template_id)}


@router.post("/targets")
async def add_target(payload: TargetCreate, user: User = Depends(get_current_user)):
    _require_admin(user)
    try:
        return {
            "status": "success",
            "data": fr.create_target(payload.points, payload.exit_pct, payload.enabled, payload.template_id),
        }
    except FrError as e:
        raise HTTPException(status_code=e.status, detail=e.message)


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
    return {"status": "success", "data": await run_in_threadpool(fr.list_symbol_maps)}


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
    fut = await run_in_threadpool(fr.resolve_futures, underlying)
    if fut is None:
        raise HTTPException(status_code=404, detail=f"No futures mapping for {underlying}")
    return {"status": "success", "data": fut}


@router.get("/expiries")
async def expiries(
    underlying: str,
    exchange: str = "NSE_INDEX",
    user: User = Depends(get_current_user),
):
    return {"status": "success", "data": await run_in_threadpool(fr.list_expiries, underlying, exchange)}


@router.get("/strikes")
async def strikes(
    underlying: str,
    expiry: str,
    option_type: str,
    exchange: str = "NSE_INDEX",
    ctx: BrokerContext = Depends(get_broker_context),
):
    data = await run_in_threadpool(
        fr.list_strikes,
        underlying, exchange, expiry, option_type,
        ctx.auth_token, ctx.broker_name, ctx.broker_config,
    )
    return {"status": "success", "data": data}


class QuickOrderPreview(BaseModel):
    underlying: str = Field(..., min_length=1)
    underlying_exchange: str = "NSE_INDEX"
    expiry: str = Field(..., min_length=1)
    ce_strike: float | None = None
    pe_strike: float | None = None


@router.post("/quick-order-preview")
async def quick_order_preview(
    payload: QuickOrderPreview,
    ctx: BrokerContext = Depends(get_broker_context),
    db: AsyncSession = Depends(get_db),
):
    """Session-auth quote preview for the browser quick-order popup.

    The popup still prefers WebSocket ticks, but this endpoint gives it a
    REST/cache fallback for instruments whose broker stream is slow or missing.
    """
    try:
        mode = await get_trading_mode(db)
        maps = [m for m in await run_in_threadpool(fr.list_symbol_maps) if m.get("enabled")]
        selected_map = next(
            (m for m in maps if str(m.get("underlying", "")).upper() == payload.underlying.upper()),
            None,
        )
        underlying_exchange = str((selected_map or {}).get("underlying_exchange") or payload.underlying_exchange)
        fut = await run_in_threadpool(fr.resolve_futures, payload.underlying)
        if fut is None:
            raise FrError(f"No futures mapping configured for {payload.underlying}", 404)

        ce: dict[str, Any] | None = None
        pe: dict[str, Any] | None = None
        instruments: list[dict[str, Any]] = [{"symbol": fut["symbol"], "exchange": fut["exchange"]}]
        if payload.ce_strike:
            ce = fr._resolve_option(  # type: ignore[attr-defined]
                payload.underlying,
                underlying_exchange,
                payload.expiry,
                "CE",
                "BUY",
                payload.ce_strike,
                "ATM",
                ctx.auth_token,
                ctx.broker_name,
                ctx.broker_config,
            )
            instruments.append({"symbol": ce["symbol"], "exchange": ce["exchange"]})
        if payload.pe_strike:
            pe = fr._resolve_option(  # type: ignore[attr-defined]
                payload.underlying,
                underlying_exchange,
                payload.expiry,
                "PE",
                "BUY",
                payload.pe_strike,
                "ATM",
                ctx.auth_token,
                ctx.broker_name,
                ctx.broker_config,
            )
            instruments.append({"symbol": pe["symbol"], "exchange": pe["exchange"]})
        quote_map = await run_in_threadpool(
            _quote_payloads, instruments, ctx.auth_token, ctx.broker_name, ctx.broker_config,
        )
        broker_error = _broker_quote_error(quote_map)
        if broker_error:
            raise HTTPException(
                status_code=broker_error["status_code"],
                detail=broker_error["body"],
            )
        data: dict[str, Any] = {
            "mode": mode,
            "futures": quote_map.get(_quote_key(fut["symbol"], fut["exchange"])),
            "ce": quote_map.get(_quote_key(ce["symbol"], ce["exchange"])) if ce else None,
            "pe": quote_map.get(_quote_key(pe["symbol"], pe["exchange"])) if pe else None,
        }
    except FrError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
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
    strike_selection_method: str | None = None
    moneyness_selection: str | None = None
    sl_points: float | None = None
    targets: list[TargetOverride] | None = None
    target_template_id: int | None = None


class ModifyTrade(BaseModel):
    # draft-only fields
    underlying: str | None = None
    underlying_exchange: str | None = None
    expiry: str | None = None
    option_type: str | None = Field(None, pattern="^(CE|PE)$")
    side: str | None = Field(None, pattern="^(BUY|SELL)$")
    product: str | None = None
    lots: int | None = Field(None, ge=1)
    strike: float | None = None
    offset: str | None = None
    # editable any time (incl. after placement)
    sl_points: float | None = Field(None, gt=0)
    targets: list[TargetOverride] | None = None
    target_template_id: int | None = None
    trailing_mode: str | None = Field(None, pattern="^(entry_after_t1|prev_target|off)$")


class PartialExit(BaseModel):
    qty: int = Field(..., ge=1)


@router.post("/trade")
async def place_trade(
    payload: PlaceTrade,
    ctx: BrokerContext = Depends(get_broker_context),
    db: AsyncSession = Depends(get_db),
):
    mode = await get_trading_mode(db)
    try:
        trade = await run_in_threadpool(
            fr.place_trade,
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


@router.post("/trade/draft")
async def create_draft(
    payload: PlaceTrade,
    ctx: BrokerContext = Depends(get_broker_context),
):
    """Create an editable draft position WITHOUT placing an order."""
    try:
        trade = fr.create_draft(
            user_id=ctx.user.id,
            auth_token=ctx.auth_token,
            broker=ctx.broker_name,
            config=ctx.broker_config,
            params=payload.model_dump(),
        )
    except FrError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    return {"status": "success", "data": trade}


@router.get("/trades")
async def list_trades(
    status: str = "all",
    mode: str | None = Query(None, pattern="^(live|sandbox)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    selected_mode = mode or await get_trading_mode(db)
    return {"status": "success", "data": await run_in_threadpool(fr.list_trades, user.id, status, mode=selected_mode)}


@router.get("/phases")
async def list_phases(
    underlying: str | None = None,
    mode: str | None = Query(None, pattern="^(live|sandbox)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Phase history grouped by (underlying, session) with per-phase lifecycle
    summary (entry/exit, P&L, duration, achieved targets, exit kind)."""
    selected_mode = mode or await get_trading_mode(db)
    return {"status": "success", "data": await run_in_threadpool(fr.list_phases, user.id, underlying, mode=selected_mode)}


@router.get("/trades/{trade_id}")
async def get_trade(
    trade_id: int,
    mode: str | None = Query(None, pattern="^(live|sandbox)$"),
    user: User = Depends(get_current_user),
):
    trade = await run_in_threadpool(fr.get_trade, user.id, trade_id, mode=mode)
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")
    return {"status": "success", "data": trade}


@router.put("/trades/{trade_id}")
async def modify_trade(
    trade_id: int,
    payload: ModifyTrade,
    ctx: BrokerContext = Depends(get_broker_context),
):
    """Modify a position before (draft: any field) or after (active: SL /
    targets / trailing) placement."""
    fields = payload.model_dump(exclude_none=True)
    if "targets" in fields:
        fields["targets"] = [t for t in fields["targets"]]
    try:
        trade = fr.modify_trade(
            ctx.user.id, trade_id, fields,
            auth_token=ctx.auth_token, broker=ctx.broker_name, config=ctx.broker_config,
        )
    except FrError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    return {"status": "success", "data": trade}


@router.post("/trades/{trade_id}/place")
async def place_draft(
    trade_id: int,
    ctx: BrokerContext = Depends(get_broker_context),
    db: AsyncSession = Depends(get_db),
):
    """Place a draft position (sends the entry order, flips it to active)."""
    mode = await get_trading_mode(db)
    try:
        trade = fr.place_draft(
            user_id=ctx.user.id, mode=mode,
            auth_token=ctx.auth_token, broker=ctx.broker_name, config=ctx.broker_config,
            trade_id=trade_id,
        )
    except FrError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    return {"status": "success", "data": trade}


@router.delete("/trades/{trade_id}")
async def delete_trade(trade_id: int, user: User = Depends(get_current_user)):
    """Delete a draft (or already-closed) trade."""
    try:
        fr.delete_trade(user.id, trade_id)
    except FrError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    return {"status": "success"}


@router.post("/trades/{trade_id}/exit")
async def exit_trade(trade_id: int, user: User = Depends(get_current_user)):
    """Full manual close of an active trade."""
    try:
        trade = await run_in_threadpool(fr.manual_exit, user.id, trade_id)
    except FrError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    return {"status": "success", "data": trade}


@router.post("/trades/{trade_id}/partial-exit")
async def partial_exit(trade_id: int, payload: PartialExit, user: User = Depends(get_current_user)):
    """Exit a specific quantity; the trade stays active if a remainder is left."""
    try:
        trade = await run_in_threadpool(fr.manual_exit, user.id, trade_id, qty=payload.qty)
    except FrError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    return {"status": "success", "data": trade}


@router.post("/trades/{trade_id}/emergency-exit")
async def emergency_exit(trade_id: int, user: User = Depends(get_current_user)):
    """Forced full close (emergency)."""
    try:
        trade = await run_in_threadpool(fr.manual_exit, user.id, trade_id, emergency=True)
    except FrError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    return {"status": "success", "data": trade}


@router.post("/trades/{trade_id}/reconcile")
async def reconcile_trade(trade_id: int, user: User = Depends(get_current_user)):
    """Refresh the recorded quantity from the live broker position book."""
    try:
        trade = await run_in_threadpool(fr.reconcile_trade, user.id, trade_id)
    except FrError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    return {"status": "success", "data": trade}


@router.post("/trades/{trade_id}/resume-exit-protection")
async def resume_exit_protection(trade_id: int, user: User = Depends(get_current_user)):
    """Verify the broker position before clearing a persistent exit block."""
    try:
        trade = await run_in_threadpool(
            lambda: fr.reconcile_trade(user.id, trade_id, force=True, resume=True)
        )
    except FrError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    return {"status": "success", "data": trade}
