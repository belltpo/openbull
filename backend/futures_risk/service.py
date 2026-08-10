"""
Futures-Risk service layer — config / target / symbol-map CRUD, option &
futures symbol resolution, and the place-trade orchestration.

Synchronous (shares ``session_scope`` with the engine). Quote/symbol lookups
reuse the existing option-symbol service helpers so we stay consistent with
the rest of OpenBull's symbology.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, text

from backend.futures_risk import defaults as fr_defaults
from backend.futures_risk.execution import dispatch_order, load_broker_context_sync, log_event
from backend.futures_risk.reconciliation import (
    PositionSnapshot,
    decide_position_reconciliation,
    get_position_snapshot,
    invalidate_position_cache,
)
from backend.futures_risk.lot_sizes import LOT_SIZE_BY_UNDERLYING, MCX_UNDERLYINGS
from backend.futures_risk.strike_selection import (
    StrikeSelectionMethod,
    normalize_method,
    normalize_moneyness,
    resolve_strike,
)
from backend.models.futures_risk import (
    FrConfig,
    FrSymbolMap,
    FrTargetLevel,
    FrTargetTemplate,
    FrTrade,
    FrTradeEvent,
    FrTradeTarget,
)
from backend.sandbox._db import session_scope
from backend.services.market_data_cache import get_ltp_value, get_market_data_cache
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

_QUICK_ORDER_STRIKE_OFFSET = 200.0
_SESSION_OPEN_CACHE: dict[tuple[str, str, str], float] = {}


def _is_mcx_underlying(underlying: str) -> bool:
    base, _ = _parse_underlying(underlying)
    return base.upper() in MCX_UNDERLYINGS


def _contract_lot_size_or_raise(underlying: str) -> int:
    base, _ = _parse_underlying(underlying)
    key = base.upper()
    lot_size = LOT_SIZE_BY_UNDERLYING.get(key)
    if lot_size is None:
        raise FrError(f"Lot size is not configured for {key}. Add it to LOT_SIZE_BY_UNDERLYING.", 400)
    return int(lot_size)


def _normalise_symbol_map_fields(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    underlying = str(out.get("underlying", "")).strip().upper()
    if _is_mcx_underlying(underlying):
        out["underlying_exchange"] = "MCX"
        out["futures_exchange"] = "MCX"
        if int(out.get("lot_size", 0) or 0) <= 0:
            out["lot_size"] = _contract_lot_size_or_raise(underlying)
    return out


def _quote_exchange_for_fr(base: str, requested_exchange: str) -> str:
    return "MCX" if _is_mcx_underlying(base) else _quote_exchange_for(base, requested_exchange)


class FrError(Exception):
    """User-facing error with an HTTP status code."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


@dataclass(frozen=True)
class ExitExecutionResult:
    ok: bool
    message: str
    order_id: str | None = None
    exited_qty: int = 0
    remaining_qty: int = 0
    fill_price: float | None = None
    pnl: float = 0.0
    reconciled: bool = False
    blocked: bool = False
    retryable: bool = False


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

            default_template = _get_or_create_default_template(db)
            if db.execute(select(func.count(FrTargetLevel.id))).scalar() == 0:
                for seq, points, pct in fr_defaults.TARGET_DEFAULTS:
                    db.add(
                        FrTargetLevel(
                            template_id=default_template.id,
                            seq=seq,
                            points=points,
                            exit_pct=pct,
                            enabled=True,
                        )
                    )

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


def _config_default(key: str, fallback: str = "") -> str:
    return fr_defaults.CONFIG_DEFAULTS.get(key, (fallback, "", True))[0]


def set_config(key: str, value: str) -> bool:
    with session_scope() as db:
        row = db.execute(select(FrConfig).where(FrConfig.key == key)).scalar_one_or_none()
        if row is None and key in fr_defaults.CONFIG_DEFAULTS:
            _, desc, editable = fr_defaults.CONFIG_DEFAULTS[key]
            row = FrConfig(key=key, value=value, description=desc, is_editable=editable)
            db.add(row)
            return editable
        if row is None or not row.is_editable:
            return False
        row.value = value
    return True


def _bool_cfg(key: str, default: bool) -> bool:
    return get_config_value(key, "true" if default else "false").strip().lower() in ("true", "1", "yes", "on")


# ---------------------------------------------------------------------------
# Target template CRUD
# ---------------------------------------------------------------------------

def _get_or_create_default_template(db) -> FrTargetTemplate:
    row = db.execute(
        select(FrTargetTemplate).where(FrTargetTemplate.is_default == True)  # noqa: E712
    ).scalar_one_or_none()
    if row is not None:
        return row
    row = db.execute(select(FrTargetTemplate).order_by(FrTargetTemplate.id).limit(1)).scalar_one_or_none()
    if row is not None:
        row.is_default = True
        row.enabled = True
        db.flush()
        return row
    row = FrTargetTemplate(
        name="Default",
        description="Default target plan",
        is_default=True,
        enabled=True,
    )
    db.add(row)
    db.flush()
    return row


def _set_default_template(db, template_id: int) -> None:
    db.execute(text("UPDATE fr_target_template SET is_default = FALSE"))
    row = db.get(FrTargetTemplate, template_id)
    if row is not None:
        row.is_default = True
        row.enabled = True


def _template_to_dict(r: FrTargetTemplate, targets: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    data = {
        "id": r.id,
        "name": r.name,
        "description": r.description or "",
        "is_default": r.is_default,
        "enabled": r.enabled,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }
    if targets is not None:
        data["targets"] = targets
    return data


def _target_to_dict(r: FrTargetLevel) -> dict[str, Any]:
    return {
        "id": r.id,
        "template_id": r.template_id,
        "seq": r.seq,
        "points": r.points,
        "exit_pct": r.exit_pct,
        "enabled": r.enabled,
    }


def _targets_for_template(db, template_id: int, enabled_only: bool = False) -> list[dict[str, Any]]:
    q = select(FrTargetLevel).where(FrTargetLevel.template_id == template_id).order_by(FrTargetLevel.seq)
    if enabled_only:
        q = q.where(FrTargetLevel.enabled == True)  # noqa: E712
    return [_target_to_dict(r) for r in db.execute(q).scalars().all()]


def list_target_templates(enabled_only: bool = False) -> list[dict[str, Any]]:
    with session_scope() as db:
        _get_or_create_default_template(db)
        q = select(FrTargetTemplate).order_by(FrTargetTemplate.is_default.desc(), FrTargetTemplate.name)
        if enabled_only:
            q = q.where(FrTargetTemplate.enabled == True)  # noqa: E712
        rows = db.execute(q).scalars().all()
        return [_template_to_dict(r, _targets_for_template(db, r.id)) for r in rows]


def get_target_template(template_id: int | None = None) -> dict[str, Any] | None:
    with session_scope() as db:
        row = _get_or_create_default_template(db) if template_id is None else db.get(FrTargetTemplate, template_id)
        if row is None:
            return None
        return _template_to_dict(row, _targets_for_template(db, row.id))


def _clean_template_targets(targets: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, t in enumerate(targets or [], start=1):
        points = float(t.get("points", 0) or 0)
        if points <= 0:
            continue
        exit_pct = float(t.get("exit_pct", 0) or 0)
        if exit_pct < 0 or exit_pct > 100:
            raise FrError("Target exit_pct must be between 0 and 100", 400)
        out.append(
            {
                "seq": len(out) + 1,
                "points": points,
                "exit_pct": exit_pct,
                "enabled": bool(t.get("enabled", True)),
            }
        )
    return _normalise_target_exit_pcts(out, enabled_key="enabled", strict=True)


def _split_exit_pcts(count: int) -> list[float]:
    if count <= 0:
        return []
    base = round(100.0 / count, 2)
    values = [base for _ in range(count)]
    values[-1] = round(100.0 - sum(values[:-1]), 2)
    return values


def _normalise_target_exit_pcts(
    targets: list[dict[str, Any]],
    *,
    enabled_key: str | None = None,
    strict: bool = False,
) -> list[dict[str, Any]]:
    """Ensure a target plan is executable and unambiguous.

    If every active target has 0%, treat it as "auto" and split 100% across
    the active target count. Otherwise the active target percentages must sum
    to 100%, because the final target exits any remaining quantity.
    """
    active_indexes = [
        idx for idx, target in enumerate(targets)
        if enabled_key is None or bool(target.get(enabled_key, True))
    ]
    if not active_indexes:
        return targets

    total = round(sum(float(targets[idx].get("exit_pct", 0) or 0) for idx in active_indexes), 2)
    if total <= 0:
        split = _split_exit_pcts(len(active_indexes))
        for idx, pct in zip(active_indexes, split, strict=False):
            targets[idx]["exit_pct"] = pct
        return targets

    if abs(total - 100.0) > 0.01:
        if strict:
            raise FrError("Enabled target exit % must total 100. Use Auto Split or adjust the target percentages.", 400)
        split = _split_exit_pcts(len(active_indexes))
        for idx, pct in zip(active_indexes, split, strict=False):
            targets[idx]["exit_pct"] = pct
    return targets


def _replace_template_targets(db, template_id: int, targets: list[dict[str, Any]]) -> None:
    db.execute(text("DELETE FROM fr_target_level WHERE template_id = :tid"), {"tid": template_id})
    for row in _clean_template_targets(targets):
        db.add(
            FrTargetLevel(
                template_id=template_id,
                seq=row["seq"],
                points=row["points"],
                exit_pct=row["exit_pct"],
                enabled=row["enabled"],
            )
        )


def create_target_template(data: dict[str, Any]) -> dict[str, Any]:
    name = str(data.get("name", "")).strip()
    if not name:
        raise FrError("Template name is required", 400)
    targets = _clean_template_targets(data.get("targets") or [])
    with session_scope() as db:
        exists = db.execute(select(FrTargetTemplate).where(FrTargetTemplate.name == name)).scalar_one_or_none()
        if exists is not None:
            raise FrError(f"Target template '{name}' already exists", 409)
        row = FrTargetTemplate(
            name=name,
            description=(data.get("description") or None),
            enabled=bool(data.get("enabled", True)),
            is_default=False,
        )
        db.add(row)
        db.flush()
        _replace_template_targets(db, row.id, targets)
        if bool(data.get("is_default", False)):
            _set_default_template(db, row.id)
        db.flush()
        return _template_to_dict(row, _targets_for_template(db, row.id))


def update_target_template(template_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    with session_scope() as db:
        row = db.get(FrTargetTemplate, template_id)
        if row is None:
            return None
        if "name" in data:
            name = str(data["name"]).strip()
            if not name:
                raise FrError("Template name is required", 400)
            duplicate = db.execute(
                select(FrTargetTemplate).where(FrTargetTemplate.name == name, FrTargetTemplate.id != template_id)
            ).scalar_one_or_none()
            if duplicate is not None:
                raise FrError(f"Target template '{name}' already exists", 409)
            row.name = name
        if "description" in data:
            row.description = data["description"] or None
        if "enabled" in data:
            if row.is_default and not bool(data["enabled"]):
                raise FrError("Default template cannot be disabled", 400)
            row.enabled = bool(data["enabled"])
        if "targets" in data and data["targets"] is not None:
            _replace_template_targets(db, row.id, data["targets"])
        if bool(data.get("is_default", False)):
            _set_default_template(db, row.id)
        db.flush()
        return _template_to_dict(row, _targets_for_template(db, row.id))


def delete_target_template(template_id: int) -> bool:
    with session_scope() as db:
        row = db.get(FrTargetTemplate, template_id)
        if row is None:
            return False
        if row.is_default:
            raise FrError("Default template cannot be deleted", 400)
        enabled_count = db.execute(
            select(func.count(FrTargetTemplate.id)).where(FrTargetTemplate.enabled == True)  # noqa: E712
        ).scalar() or 0
        if enabled_count <= 1 and row.enabled:
            raise FrError("At least one enabled target template is required", 400)
        db.delete(row)
    return True


def list_targets(enabled_only: bool = False, template_id: int | None = None) -> list[dict[str, Any]]:
    with session_scope() as db:
        template = _get_or_create_default_template(db) if template_id is None else db.get(FrTargetTemplate, template_id)
        if template is None:
            return []
        return _targets_for_template(db, template.id, enabled_only=enabled_only)


def create_target(points: float, exit_pct: float, enabled: bool = True, template_id: int | None = None) -> dict[str, Any]:
    with session_scope() as db:
        template = _get_or_create_default_template(db) if template_id is None else db.get(FrTargetTemplate, template_id)
        if template is None:
            raise FrError("Target template not found", 404)
        max_seq = db.execute(
            select(func.max(FrTargetLevel.seq)).where(FrTargetLevel.template_id == template.id)
        ).scalar() or 0
        row = FrTargetLevel(
            template_id=template.id,
            seq=int(max_seq) + 1,
            points=float(points),
            exit_pct=float(exit_pct),
            enabled=bool(enabled),
        )
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
        template_id = row.template_id
        db.delete(row)
        db.flush()
        # Re-sequence remaining rows to stay contiguous (1..n). Two-phase to
        # avoid colliding with the unique index on seq.
        remaining = db.execute(
            select(FrTargetLevel)
            .where(FrTargetLevel.template_id == template_id)
            .order_by(FrTargetLevel.seq)
        ).scalars().all()
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
    data = _normalise_symbol_map_fields(
        {
            "underlying": r.underlying,
            "underlying_exchange": r.underlying_exchange,
            "futures_symbol": r.futures_symbol,
            "futures_exchange": r.futures_exchange,
            "lot_size": r.lot_size,
            "auto_resolve": r.auto_resolve,
            "enabled": r.enabled,
        }
    )
    return {
        "id": r.id,
        **data,
    }


def list_symbol_maps() -> list[dict[str, Any]]:
    with session_scope() as db:
        rows = db.execute(select(FrSymbolMap).order_by(FrSymbolMap.underlying)).scalars().all()
        return [_map_to_dict(r) for r in rows]


def create_symbol_map(data: dict[str, Any]) -> dict[str, Any]:
    data = _normalise_symbol_map_fields(data)
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
        data = _normalise_symbol_map_fields({**_map_to_dict(row), **data})
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
        normalised = _normalise_symbol_map_fields(_map_to_dict(row))
        fexch = str(normalised["futures_exchange"])
        lot = int(normalised["lot_size"] or 0)
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
    options_exchange = _option_exchange_for(_quote_exchange_for_fr(base, underlying_exchange))
    with session_scope() as db:
        rows = db.execute(
            text(
                "SELECT symbol, expiry FROM symtoken "
                "WHERE symbol LIKE :prefix AND exchange = :exch "
                "AND instrumenttype IN ('CE','PE') AND expiry IS NOT NULL AND expiry != ''"
            ),
            {"prefix": f"{base}%", "exch": options_exchange},
        ).fetchall()
    exact_pattern = re.compile(
        rf"^{re.escape(base.upper())}\d{{2}}[A-Z]{{3}}\d{{2}}\d+(?:\.\d+)?(?:CE|PE)$"
    )
    expiries = {
        exp
        for sym, exp in rows
        if sym and exp and exact_pattern.match(str(sym).upper())
    }
    out: list[tuple[datetime, str]] = []
    today_ist = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    for exp in expiries:
        try:
            d = datetime.strptime(exp, "%d-%b-%y")
        except (ValueError, TypeError):
            continue
        if d.date() < today_ist:
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
    quote_exchange = _quote_exchange_for_fr(base, underlying_exchange)
    options_exchange = _option_exchange_for(quote_exchange)
    strikes = _fetch_available_strikes(base, expiry.upper(), option_type.upper(), options_exchange)

    atm: float | None = None
    open_atm: float | None = None

    def positive_float(value: Any) -> float | None:
        try:
            out = float(value or 0)
        except (TypeError, ValueError):
            return None
        return out if out > 0 else None

    def fresh_cached_ltp(symbol: str, exchange: str) -> float | None:
        try:
            entry = get_market_data_cache().get_all(symbol, exchange)
            last_update = float(entry.get("last_update") or 0)
            ltp = positive_float((entry.get("ltp") or {}).get("value"))
        except Exception:
            return None
        if ltp is None or last_update <= 0:
            return None
        return ltp if time.time() - last_update <= 5 else None

    def cached_open(symbol: str, exchange: str) -> float | None:
        try:
            entry = get_market_data_cache().get_all(symbol, exchange)
            last_update = float(entry.get("last_update") or 0)
            opened = positive_float((entry.get("quote") or {}).get("open"))
        except Exception:
            return None
        if opened is None or last_update <= 0:
            return None
        # The session open is stable, but require a recent quote so stale
        # previous-day cache cannot drive today's quick-order default strikes.
        return opened if time.time() - last_update <= 300 else None

    try:
        if quote_exchange in ("NSE_INDEX", "BSE_INDEX", "NSE", "BSE"):
            quote_symbol, q_exch = base, quote_exchange
        else:
            fut = _find_near_month_futures(base, quote_exchange)
            quote_symbol, q_exch = (fut["symbol"], fut["exchange"]) if fut else (base, quote_exchange)
        open_cache_key = (datetime.now().date().isoformat(), quote_symbol.upper(), q_exch.upper())
        open_price = _SESSION_OPEN_CACHE.get(open_cache_key) or cached_open(quote_symbol, q_exch)
        if open_price:
            _SESSION_OPEN_CACHE[open_cache_key] = open_price
        cached_ltp = fresh_cached_ltp(quote_symbol, q_exch)
        if cached_ltp:
            atm = _find_atm(cached_ltp, strikes)

        if not cached_ltp or not open_price:
            ok, q, _ = get_quotes_with_auth(quote_symbol, q_exch, auth_token, broker, config)
            if ok:
                quote_data = q.get("data", {})
                open_price = open_price or positive_float(quote_data.get("open"))
                if open_price:
                    _SESSION_OPEN_CACHE[open_cache_key] = open_price
                ltp = positive_float(quote_data.get("ltp")) if not cached_ltp else None
                if atm is None and ltp:
                    atm = _find_atm(ltp, strikes)
        if open_price:
            open_atm = _find_atm(open_price, strikes)
        if atm is None:
            # If REST is rate-limited or unavailable, an older cache value is
            # still useful for strike selection. Live display never uses this
            # fallback; it is only an ATM selector.
            cached_ltp = get_ltp_value(quote_symbol, q_exch)
            if cached_ltp:
                atm = _find_atm(float(cached_ltp), strikes)
    except Exception:
        logger.exception("ATM lookup failed for %s", underlying)

    reference_atm = open_atm or atm
    ce_default_strike = _find_atm(reference_atm - _QUICK_ORDER_STRIKE_OFFSET, strikes) if reference_atm else None
    pe_default_strike = _find_atm(reference_atm + _QUICK_ORDER_STRIKE_OFFSET, strikes) if reference_atm else None
    return {
        "strikes": strikes,
        "atm": atm,
        "open_atm": open_atm,
        "ce_default_strike": ce_default_strike,
        "pe_default_strike": pe_default_strike,
        "options_exchange": options_exchange,
    }


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
    options_exchange = _option_exchange_for(_quote_exchange_for_fr(base, underlying_exchange))

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


def _resolve_selected_strike(
    p: dict[str, Any],
    auth_token: str,
    broker: str,
    config: dict | None,
) -> float | None:
    """Resolve the persisted selector to an absolute strike at order time."""
    raw_method = p.get("strike_selection_method")
    if not raw_method:
        return p.get("strike")

    method = normalize_method(raw_method)
    if method == StrikeSelectionMethod.MANUAL:
        try:
            return resolve_strike(
                method=method,
                option_type=p["option_type"],
                strikes=[],
                atm=None,
                manual_strike=p.get("strike"),
            )
        except ValueError as exc:
            raise FrError(str(exc), 422) from exc

    data = list_strikes(
        p["underlying"],
        p["underlying_exchange"],
        p["expiry"],
        p["option_type"],
        auth_token,
        broker,
        config,
    )
    try:
        selected = resolve_strike(
            method=method,
            option_type=p["option_type"],
            strikes=[float(s) for s in data.get("strikes") or []],
            atm=float(data["atm"]) if data.get("atm") else None,
            moneyness=normalize_moneyness(p.get("moneyness_selection")),
            offset_strike=(
                data.get("ce_default_strike")
                if p["option_type"] == "CE"
                else data.get("pe_default_strike")
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise FrError(str(exc), 422) from exc
    return selected


def _build_targets(
    entry_fut: float,
    direction: int,
    lots: int,
    lot_size: int,
    template: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Snapshot target rows: trigger price + whole-lot exit qty per target.

    Percentages are converted to whole lots because F&O exits must be lot-sized.
    A trade cannot have more executable targets than lots. For example, 2 lots
    with a 4-target template creates only T1/T2, with each target receiving an
    executable lot allocation.
    """
    out: list[dict[str, Any]] = []
    lots = max(0, int(lots or 0))
    if lots <= 0:
        return out

    active_targets = [dict(t) for t in template if float(t.get("points", 0) or 0) > 0]
    if len(active_targets) > lots:
        active_targets = active_targets[:lots]
        total_pct = round(sum(float(t.get("exit_pct", 0) or 0) for t in active_targets), 2)
        if total_pct <= 0:
            base_pct = round(100.0 / len(active_targets), 2)
            used_pct = 0.0
            for idx, target in enumerate(active_targets):
                target["exit_pct"] = round(100.0 - used_pct, 2) if idx == len(active_targets) - 1 else base_pct
                used_pct += float(target["exit_pct"])
        else:
            used_pct = 0.0
            for idx, target in enumerate(active_targets):
                pct = round((float(target.get("exit_pct", 0) or 0) / total_pct) * 100.0, 2)
                target["exit_pct"] = round(100.0 - used_pct, 2) if idx == len(active_targets) - 1 else pct
                used_pct += float(target["exit_pct"])

    lots_used = 0
    for idx, t in enumerate(active_targets):
        points = float(t["points"])
        pct = float(t.get("exit_pct", 0))
        lots_i = int((lots * pct) // 100)  # floor to whole lots
        is_final_target = idx == len(active_targets) - 1
        remaining_targets = len(active_targets) - idx
        remaining_lots = lots - lots_used
        if remaining_lots <= 0:
            break
        if lots_i < 1:
            lots_i = 1
        max_lots_for_this_target = max(1, remaining_lots - (remaining_targets - 1))
        if lots_i > max_lots_for_this_target and not is_final_target:
            lots_i = max_lots_for_this_target
        if is_final_target:
            lots_i = max(lots_i, lots - lots_used)
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
        "product": str(params.get("product") or get_config_value("default_product", _config_default("default_product"))).upper(),
        "strike": strike,
        "strike_selection_method": params.get("strike_selection_method"),
        "moneyness_selection": normalize_moneyness(params.get("moneyness_selection")).value,
        "offset": params.get("offset") or "ATM",
        "sl_points": sl_points,
        "targets": params.get("targets") or None,
        "target_template_id": int(params["target_template_id"]) if params.get("target_template_id") not in (None, "", 0, "0") else None,
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
    selected_strike = _resolve_selected_strike(p, auth_token, broker, config)
    opt = _resolve_option(
        p["underlying"], p["underlying_exchange"], p["expiry"], p["option_type"],
        p["side"], selected_strike, p["offset"], auth_token, broker, config,
    )

    # 2) Futures contract + entry futures price
    fut = resolve_futures(p["underlying"])
    if fut is None:
        raise FrError(
            f"No futures mapping configured for {p['underlying']}. Add one in the admin panel.", 400
        )
    entry_fut = 0.0
    status = 0
    try:
        cached_entry = get_ltp_value(fut["symbol"], fut["exchange"])
        if cached_entry and float(cached_entry) > 0:
            entry_fut = float(cached_entry)
    except Exception:
        pass
    if entry_fut <= 0:
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
            if entry_opt > 0:
                try:
                    from backend.services.market_data_cache import process_market_data

                    process_market_data({
                        "symbol": opt["symbol"],
                        "exchange": opt["exchange"],
                        "mode": 1,
                        "data": {"ltp": entry_opt, "timestamp": time.time(), "volume": 0},
                    })
                except Exception:
                    logger.debug(
                        "Unable to seed market-data cache for %s/%s",
                        opt["symbol"],
                        opt["exchange"],
                        exc_info=True,
                    )
    except Exception:
        pass

    # 3) Direction + SL + targets
    direction = 1 if (p["option_type"] == "CE") == (p["side"] == "BUY") else -1
    sl_points = p["sl_points"]
    if sl_points is None:
        sl_points = float(get_config_value("default_sl_points", _config_default("default_sl_points")))
    sl_price = round(entry_fut - direction * sl_points, 2) if entry_fut > 0 else 0.0

    if p["targets"]:
        template = _normalise_target_exit_pcts([
            {"seq": i + 1, "points": float(t["points"]), "exit_pct": float(t.get("exit_pct", 0))}
            for i, t in enumerate(p["targets"])
            if float(t.get("points", 0)) > 0
        ])
    else:
        template = _normalise_target_exit_pcts(list_targets(enabled_only=True, template_id=p.get("target_template_id")))
    if not template:
        raise FrError("No targets configured for the selected template.", 400)
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


def _session_date_ist() -> str:
    """IST trading date (YYYY-MM-DD) used as the phase-group session key."""
    ist = datetime.now(tz=timezone.utc) + timedelta(hours=5, minutes=30)
    return ist.date().isoformat()


def _session_date_for_dt(dt: datetime | None) -> str:
    """Return the IST trading date for a persisted UTC timestamp."""
    if dt is None:
        return _session_date_ist()
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return (dt + timedelta(hours=5, minutes=30)).date().isoformat()


def _normalize_mode_filter(mode: str | None) -> str | None:
    if mode is None:
        return None
    value = str(mode).strip().lower()
    return value if value in {"live", "sandbox"} else None


def _phase_group_key(user_id: int, underlying: str, session_date: str, mode: str | None = None) -> str:
    normalized = _normalize_mode_filter(mode)
    if normalized:
        return f"{user_id}:{normalized}:{underlying}:{session_date}"
    return f"{user_id}:{underlying}:{session_date}"


def _display_phase_group(user_id: int, underlying: str, created_at: datetime | None, mode: str | None = None) -> str:
    return _phase_group_key(user_id, underlying, _session_date_for_dt(created_at), mode)


def _assign_phase(db, user_id: int, underlying: str, mode: str | None = None) -> tuple[str, int]:
    """Return (phase_group, next_phase_no) for this instrument's IST session."""
    session_date = _session_date_ist()
    normalized_mode = _normalize_mode_filter(mode)
    group = _phase_group_key(user_id, underlying, session_date, normalized_mode)
    q = select(FrTrade.created_at).where(
        FrTrade.user_id == user_id,
        FrTrade.underlying == underlying,
        FrTrade.phase_no > 0,
    )
    if normalized_mode:
        q = q.where(FrTrade.mode == normalized_mode)
    rows = db.execute(q.order_by(FrTrade.created_at, FrTrade.id)).scalars().all()
    same_day_count = sum(1 for created_at in rows if _session_date_for_dt(created_at) == session_date)
    return group, same_day_count + 1


def _assert_no_active_phase(
    db,
    user_id: int,
    underlying: str,
    exclude_trade_id: int | None = None,
    mode: str | None = None,
) -> None:
    normalized_mode = _normalize_mode_filter(mode)
    q = select(FrTrade).where(
        FrTrade.user_id == user_id,
        FrTrade.underlying == underlying,
        FrTrade.status == "active",
    )
    if normalized_mode:
        q = q.where(FrTrade.mode == normalized_mode)
    if exclude_trade_id is not None:
        q = q.where(FrTrade.id != exclude_trade_id)
    existing = db.execute(q.order_by(FrTrade.phase_no.desc()).limit(1)).scalar_one_or_none()
    if existing is not None:
        display_phase = _phase_display_numbers(db, user_id, normalized_mode).get(existing.id, existing.phase_no)
        raise FrError(
            f"{underlying} Phase {display_phase} is still active. Complete it before starting the next phase.",
            409,
        )


def _pnl_quantity(t: FrTrade, qty: int) -> int:
    """Quantity to use for rupee P&L without changing broker order quantity.

    Broker order quantity stays untouched. This function only corrects MTM/P&L
    when a broker or stale symbol map persisted quantity as lot count instead
    of exchange quantity.
    """
    raw_qty = max(0, int(qty or 0))
    stored_lot_size = int(t.lot_size or 0)
    stored_total_qty = int(t.total_qty or 0)
    stored_lots = int(t.lots or 0)
    looks_like_lots = stored_lot_size <= 1 or (stored_lots > 0 and stored_total_qty <= stored_lots)
    if looks_like_lots:
        return raw_qty * _contract_lot_size_or_raise(str(t.underlying or ""))
    return raw_qty


def _leg_exit_pnl(side: str, entry_opt: float, exit_opt: float, qty: int) -> float:
    """Realized P&L for exiting ``qty`` of the option leg at ``exit_opt``."""
    if exit_opt <= 0 or entry_opt <= 0 or qty <= 0:
        return 0.0
    delta = (exit_opt - entry_opt) if side == "BUY" else (entry_opt - exit_opt)
    return round(delta * qty, 2)


def _trade_exit_pnl(t: FrTrade, exit_opt: float, qty: int) -> float:
    return _leg_exit_pnl(t.side, t.entry_option_price, exit_opt, _pnl_quantity(t, qty))


def _option_exit_price(symbol: str, exchange: str, fallback: float = 0.0) -> float:
    """Best-effort current option premium (MarketDataCache → fallback)."""
    try:
        val = get_ltp_value(symbol, exchange)
        if val and float(val) > 0:
            return float(val)
    except Exception:
        pass
    return float(fallback)


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


def _persist_failed_entry(
    *,
    user_id: int,
    mode: str,
    params: dict[str, Any],
    plan: dict[str, Any],
    message: str,
    broker_status: int,
    existing_trade_id: int | None = None,
) -> int:
    """Store a rejected entry attempt with its resolved SL/target levels.

    Failed entries must be visible for audit/debugging, but they must never be
    treated as active positions or consume a phase number.
    """
    with session_scope() as db:
        if existing_trade_id is not None:
            trade = db.get(FrTrade, existing_trade_id)
            if trade is None or trade.user_id != user_id:
                raise FrError("Draft not found", 404)
        else:
            trade = FrTrade(user_id=user_id)
            db.add(trade)

        trade.mode = mode
        trade.underlying = params["underlying"]
        trade.option_symbol = plan["option_symbol"]
        trade.option_exchange = plan["option_exchange"]
        trade.option_type = params["option_type"]
        trade.side = params["side"]
        trade.product = params["product"]
        trade.expiry = params["expiry"]
        trade.strike = plan["strike_val"]
        trade.lots = params["lots"]
        trade.lot_size = plan["lot_size"]
        trade.total_qty = plan["total_qty"]
        trade.remaining_qty = 0
        trade.entry_option_price = plan["entry_opt"]
        trade.entry_order_id = None
        trade.futures_symbol = plan["fut_symbol"]
        trade.futures_exchange = plan["fut_exchange"]
        trade.entry_futures_price = plan["entry_fut"]
        trade.direction = plan["direction"]
        trade.sl_points = plan["sl_points"]
        trade.sl_price = plan["sl_price"]
        trade.sl_basis = "initial"
        trade.status = "error"
        trade.realized_pnl = 0.0
        trade.closed_at = datetime.now(tz=timezone.utc)
        trade.modified_by = user_id
        if existing_trade_id is None:
            trade.created_by = user_id
        trade.phase_group = None
        trade.phase_no = 0
        trade.meta = {
            "offset": params["offset"] if params["strike"] is None else None,
            "params": params,
            "entry_error": message,
            "broker_status": broker_status,
        }
        db.flush()

        db.execute(text("DELETE FROM fr_trade_target WHERE trade_id = :tid"), {"tid": trade.id})
        _persist_targets(db, trade.id, plan["target_rows"])
        log_event(
            db,
            trade_id=trade.id,
            user_id=user_id,
            kind="error",
            severity="error",
            message=f"Entry order failed: {message}",
            payload={
                "broker_status": broker_status,
                "entry_futures_price": plan["entry_fut"],
                "entry_option_price": plan["entry_opt"],
                "sl_price": plan["sl_price"],
                "targets": plan["target_rows"],
            },
        )
        return trade.id


_ENTRY_SUCCESS_STATUSES = {"complete", "completed", "traded", "filled", "success"}
_ENTRY_FAILURE_STATUSES = {"rejected", "cancelled", "canceled", "failed"}


def _coerce_positive_float(value: Any) -> float | None:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return num if num > 0 else None


def _extract_order_fill_price(data: dict[str, Any]) -> float | None:
    for key in (
        "average_price",
        "avg_price",
        "averagePrice",
        "avgPrice",
        "filled_price",
        "fill_price",
        "traded_price",
        "tradedPrice",
        "execution_price",
    ):
        price = _coerce_positive_float(data.get(key))
        if price is not None:
            return price
    return None


def _apply_sandbox_fill_price(plan: dict[str, Any], response: dict[str, Any]) -> None:
    """Use the simulator fill, rather than an advisory pre-order quote."""
    fill_price = _extract_order_fill_price(response)
    if fill_price is not None:
        plan["entry_opt"] = fill_price


def _broker_order_status(
    order_id: str,
    auth_token: str,
    broker: str,
    config: dict | None,
) -> tuple[str | None, str | None, float | None]:
    try:
        from backend.services.orderstatus_service import get_orderstatus_with_auth

        ok, resp, _ = get_orderstatus_with_auth(order_id, auth_token, broker, config)
    except Exception as exc:
        logger.debug("Entry order status check failed for %s: %s", order_id, exc)
        return None, None, None
    if not ok:
        return None, resp.get("message") if isinstance(resp, dict) else None, None
    data = resp.get("data") if isinstance(resp, dict) else None
    if not isinstance(data, dict):
        return None, None, None
    raw_status = data.get("order_status") or data.get("status")
    status = str(raw_status).strip().lower() if raw_status is not None else None
    return status, None, _extract_order_fill_price(data)


def _confirm_entry_order(
    order_id: str,
    auth_token: str,
    broker: str,
    config: dict | None,
    *,
    attempts: int = 6,
    delay_sec: float = 0.35,
) -> tuple[bool, str | None, float | None]:
    last_status: str | None = None
    last_error: str | None = None
    fill_price: float | None = None
    for attempt in range(attempts):
        status, err, price = _broker_order_status(order_id, auth_token, broker, config)
        last_status = status or last_status
        last_error = err or last_error
        fill_price = price or fill_price
        if status in _ENTRY_SUCCESS_STATUSES:
            return True, None, fill_price
        if status in _ENTRY_FAILURE_STATUSES:
            return False, f"Broker order {order_id} was {status}", fill_price
        if attempt < attempts - 1:
            time.sleep(delay_sec)
    if last_status:
        return False, f"Broker order {order_id} did not complete; current status is {last_status}", fill_price
    return False, last_error or f"Broker order {order_id} status could not be confirmed", fill_price


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
    with session_scope() as db:
        _assert_no_active_phase(db, user_id, p["underlying"], mode=mode)
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
    entry_order_id = resp.get("orderid")
    if not ok:
        msg = resp.get("message", "Entry order failed")
        trade_id = _persist_failed_entry(
            user_id=user_id,
            mode=mode,
            params=p,
            plan=plan,
            message=msg,
            broker_status=status,
        )
        return get_trade(user_id, trade_id) or {}
    if mode != "sandbox" and not entry_order_id:
        trade_id = _persist_failed_entry(
            user_id=user_id,
            mode=mode,
            params=p,
            plan=plan,
            message="Broker did not return an order id",
            broker_status=status,
        )
        return get_trade(user_id, trade_id) or {}
    if mode == "sandbox":
        _apply_sandbox_fill_price(plan, resp)
    else:
        confirmed, confirm_message, fill_price = _confirm_entry_order(str(entry_order_id), auth_token, broker, config)
        if not confirmed:
            trade_id = _persist_failed_entry(
                user_id=user_id,
                mode=mode,
                params=p,
                plan=plan,
                message=confirm_message or "Broker entry order was not completed",
                broker_status=status,
            )
            return get_trade(user_id, trade_id) or {}
        if fill_price is not None:
            plan["entry_opt"] = fill_price

    with session_scope() as db:
        group, phase_no = _assign_phase(db, user_id, p["underlying"], mode)
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
            phase_group=group,
            phase_no=phase_no,
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
            message=f"{p['side']} {p['lots']} lot(s) {plan['option_symbol']} @ MKT | entry futures {plan['entry_fut']} | SL {plan['sl_price']} | Phase {phase_no}",
            payload={"entry_order_id": entry_order_id, "futures": plan["fut_symbol"], "entry_futures_price": plan["entry_fut"], "phase_no": phase_no},
        )
        if phase_no > 1:
            log_event(
                db, trade_id=trade.id, user_id=user_id, kind="phase_change",
                message=f"Phase {phase_no} started on {p['underlying']}",
                payload={"phase_no": phase_no, "phase_group": group},
            )
        trade_id = trade.id

    try:
        from backend.futures_risk import engine as fr_engine

        fr_engine.ensure_symbols_streaming([
            {"symbol": plan["fut_symbol"], "exchange": plan["fut_exchange"]},
            {"symbol": plan["option_symbol"], "exchange": plan["option_exchange"]},
        ])
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
    with session_scope() as db:
        _assert_no_active_phase(db, user_id, p["underlying"], exclude_trade_id=trade_id, mode=mode)
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
    entry_order_id = resp.get("orderid")
    if not ok:
        msg = resp.get("message", "Entry order failed")
        failed_id = _persist_failed_entry(
            user_id=user_id,
            mode=mode,
            params=p,
            plan=plan,
            message=msg,
            broker_status=status,
            existing_trade_id=trade_id,
        )
        return get_trade(user_id, failed_id) or {}
    if mode != "sandbox" and not entry_order_id:
        failed_id = _persist_failed_entry(
            user_id=user_id,
            mode=mode,
            params=p,
            plan=plan,
            message="Broker did not return an order id",
            broker_status=status,
            existing_trade_id=trade_id,
        )
        return get_trade(user_id, failed_id) or {}
    if mode == "sandbox":
        _apply_sandbox_fill_price(plan, resp)
    else:
        confirmed, confirm_message, fill_price = _confirm_entry_order(str(entry_order_id), auth_token, broker, config)
        if not confirmed:
            failed_id = _persist_failed_entry(
                user_id=user_id,
                mode=mode,
                params=p,
                plan=plan,
                message=confirm_message or "Broker entry order was not completed",
                broker_status=status,
                existing_trade_id=trade_id,
            )
            return get_trade(user_id, failed_id) or {}
        if fill_price is not None:
            plan["entry_opt"] = fill_price

    with session_scope() as db:
        t = db.get(FrTrade, trade_id)
        group, phase_no = _assign_phase(db, user_id, p["underlying"], mode)
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
        t.phase_group = group
        t.phase_no = phase_no
        # Rebuild target snapshot off the real entry price.
        db.execute(
            text("DELETE FROM fr_trade_target WHERE trade_id = :tid"), {"tid": trade_id}
        )
        _persist_targets(db, trade_id, plan["target_rows"])
        log_event(
            db, trade_id=trade_id, user_id=user_id, kind="entry",
            message=f"Draft placed: {p['side']} {p['lots']} lot(s) {plan['option_symbol']} @ MKT | entry futures {plan['entry_fut']} | SL {plan['sl_price']} | Phase {phase_no}",
            payload={"entry_order_id": entry_order_id, "entry_futures_price": plan["entry_fut"], "phase_no": phase_no},
        )
        if phase_no > 1:
            log_event(
                db, trade_id=trade_id, user_id=user_id, kind="phase_change",
                message=f"Phase {phase_no} started on {p['underlying']}",
                payload={"phase_no": phase_no, "phase_group": group},
            )

    try:
        from backend.futures_risk import engine as fr_engine

        fr_engine.ensure_symbols_streaming([
            {"symbol": plan["fut_symbol"], "exchange": plan["fut_exchange"]},
            {"symbol": plan["option_symbol"], "exchange": plan["option_exchange"]},
        ])
    except Exception:
        logger.debug("ensure_streaming skipped", exc_info=True)

    return get_trade(user_id, trade_id) or {}


# ---------------------------------------------------------------------------
# Reads / serialization
# ---------------------------------------------------------------------------

def _utc_iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _epoch_ms(dt: datetime | None) -> int | None:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _trade_to_dict(t: FrTrade) -> dict[str, Any]:
    live_option_price = None
    if t.option_symbol and t.option_exchange:
        try:
            live_option_price = get_ltp_value(t.option_symbol, t.option_exchange)
        except Exception:
            live_option_price = None
    pnl_qty = _pnl_quantity(t, int(t.remaining_qty or 0))
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
        "pnl_qty": pnl_qty,
        "entry_option_price": t.entry_option_price,
        "live_option_price": live_option_price,
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
        "exit_state": t.exit_state or "idle",
        "exit_attempt_reason": t.exit_attempt_reason,
        "exit_attempted_at": _utc_iso(t.exit_attempted_at),
        "exit_failure_count": int(t.exit_failure_count or 0),
        "exit_block_reason": t.exit_block_reason,
        "last_exit_order_id": t.last_exit_order_id,
        "broker_remaining_qty": t.broker_remaining_qty,
        "broker_reconciled_at": _utc_iso(t.broker_reconciled_at),
        "created_by": t.created_by,
        "modified_by": t.modified_by,
        "params": (t.meta or {}).get("params"),
        "trailing_mode": (t.meta or {}).get("trailing_mode"),
        "phase_group": t.phase_group,
        "phase_no": t.phase_no,
        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        "duration_sec": (
            int(((t.closed_at or t.updated_at) - t.created_at).total_seconds())
            if t.created_at and (t.closed_at or t.updated_at)
            else None
        ),
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "created_at_utc": _utc_iso(t.created_at),
        "created_at_epoch_ms": _epoch_ms(t.created_at),
        "entry_time": _utc_iso(t.created_at),
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def _trade_exit_option_prices(db, trade_id: int) -> tuple[dict[int, float], float | None]:
    """Extract option execution prices recorded in trade events.

    The target table stores futures trigger levels, while option exit prices are
    logged in event payloads at execution time. Keep this helper read-only so
    existing rows do not need a schema migration.
    """
    rows = db.execute(
        select(FrTradeEvent.kind, FrTradeEvent.payload)
        .where(
            FrTradeEvent.trade_id == trade_id,
            FrTradeEvent.kind.in_(("target_hit", "sl_hit")),
        )
        .order_by(FrTradeEvent.ts)
    ).all()
    target_prices: dict[int, float] = {}
    sl_price: float | None = None
    for kind, payload in rows:
        if not isinstance(payload, dict):
            continue
        raw_price = payload.get("exit_option_price")
        if raw_price is None:
            continue
        try:
            price = float(raw_price)
        except (TypeError, ValueError):
            continue
        if kind == "target_hit":
            try:
                seq = int(payload.get("seq"))
            except (TypeError, ValueError):
                continue
            target_prices[seq] = price
        elif kind == "sl_hit":
            sl_price = price
    existing_target_price_seqs = list(target_prices) or [-1]
    missing_hit_prices = db.execute(
        select(FrTradeTarget.seq)
        .where(
            FrTradeTarget.trade_id == trade_id,
            FrTradeTarget.status == "hit",
            ~FrTradeTarget.seq.in_(existing_target_price_seqs),
        )
        .order_by(FrTradeTarget.seq)
    ).scalars().all()
    if missing_hit_prices:
        trade = db.get(FrTrade, trade_id)
        if trade is not None:
            current_option_ltp = get_ltp_value(trade.option_symbol, trade.option_exchange)
            if current_option_ltp and float(current_option_ltp) > 0:
                for seq in missing_hit_prices:
                    target_prices[int(seq)] = float(current_option_ltp)
    return target_prices, sl_price


def _target_row_to_dict(r: FrTradeTarget, exit_option_price: float | None = None) -> dict[str, Any]:
    return {
        "seq": r.seq,
        "points": r.points,
        "exit_pct": r.exit_pct,
        "trigger_price": r.trigger_price,
        "exit_qty": r.exit_qty,
        "status": r.status,
        "hit_futures_price": r.hit_futures_price,
        "exit_order_id": r.exit_order_id,
        "exit_option_price": exit_option_price,
        "hit_at": r.hit_at.isoformat() if r.hit_at else None,
    }


def _mark_missing_entry_order_ids_failed(db, user_id: int) -> None:
    rows = db.execute(
        select(FrTrade).where(
            FrTrade.user_id == user_id,
            FrTrade.mode == "live",
            FrTrade.status == "active",
            FrTrade.entry_order_id.is_(None),
        )
    ).scalars().all()
    for trade in rows:
        trade.status = "error"
        trade.remaining_qty = 0
        trade.closed_at = datetime.now(tz=timezone.utc)
        meta = dict(trade.meta or {})
        meta.setdefault("entry_error", "Broker order id missing; marking as failed")
        trade.meta = meta
        log_event(
            db,
            trade_id=trade.id,
            user_id=user_id,
            kind="error",
            severity="error",
            message="Entry order failed: broker order id missing",
            payload={
                "entry_futures_price": trade.entry_futures_price,
                "entry_option_price": trade.entry_option_price,
                "sl_price": trade.sl_price,
            },
        )


def _sync_active_entry_order_statuses(db, user_id: int) -> None:
    ctx = load_broker_context_sync(user_id)
    if not ctx:
        return
    rows = db.execute(
        select(FrTrade).where(
            FrTrade.user_id == user_id,
            FrTrade.mode == "live",
            FrTrade.status == "active",
            FrTrade.entry_order_id.is_not(None),
        )
    ).scalars().all()
    for trade in rows:
        status, _, _ = _broker_order_status(
            str(trade.entry_order_id),
            ctx["auth_token"],
            ctx["broker"],
            ctx.get("config"),
        )
        if status not in _ENTRY_FAILURE_STATUSES:
            continue
        trade.status = "error"
        trade.remaining_qty = 0
        trade.closed_at = datetime.now(tz=timezone.utc)
        meta = dict(trade.meta or {})
        meta["entry_error"] = f"Broker entry order {trade.entry_order_id} was {status}"
        trade.meta = meta
        log_event(
            db,
            trade_id=trade.id,
            user_id=user_id,
            kind="error",
            severity="error",
            message=f"Entry order failed: broker order {trade.entry_order_id} was {status}",
            payload={
                "entry_order_id": trade.entry_order_id,
                "broker_status": status,
                "entry_futures_price": trade.entry_futures_price,
                "entry_option_price": trade.entry_option_price,
                "sl_price": trade.sl_price,
            },
        )


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


def _phase_display_numbers(db, user_id: int, mode: str | None = None) -> dict[int, int]:
    normalized_mode = _normalize_mode_filter(mode)
    q = select(FrTrade).where(FrTrade.user_id == user_id, FrTrade.phase_no > 0)
    if normalized_mode:
        q = q.where(FrTrade.mode == normalized_mode)
    rows = db.execute(q.order_by(FrTrade.created_at, FrTrade.id)).scalars().all()
    counters: dict[tuple[str, str, str], int] = {}
    out: dict[int, int] = {}
    for trade in rows:
        key = (trade.mode, trade.underlying, _session_date_for_dt(trade.created_at))
        counters[key] = counters.get(key, 0) + 1
        out[trade.id] = counters[key]
    return out


def list_trades(user_id: int, status: str | None = None, mode: str | None = None) -> list[dict[str, Any]]:
    with session_scope() as db:
        _mark_missing_entry_order_ids_failed(db, user_id)
        _sync_active_entry_order_statuses(db, user_id)
        normalized_mode = _normalize_mode_filter(mode)
        q = select(FrTrade).where(FrTrade.user_id == user_id)
        if normalized_mode:
            q = q.where(FrTrade.mode == normalized_mode)
        if status and status != "all":
            q = q.where(FrTrade.status == status)
        q = q.order_by(FrTrade.created_at.desc())
        trades = db.execute(q).scalars().all()
        display_phase = _phase_display_numbers(db, user_id, normalized_mode)
        out = []
        for t in trades:
            d = _trade_to_dict(t)
            target_exit_prices, sl_exit_option_price = _trade_exit_option_prices(db, t.id)
            d["sl_exit_option_price"] = sl_exit_option_price
            d["sl_hit"] = bool(
                sl_exit_option_price is not None
                or db.execute(
                    select(FrTradeEvent.id)
                    .where(FrTradeEvent.trade_id == t.id, FrTradeEvent.kind == "sl_hit")
                    .limit(1)
                ).scalar()
            )
            if t.id in display_phase:
                d["phase_group"] = _display_phase_group(user_id, t.underlying, t.created_at, t.mode)
                d["phase_no"] = display_phase[t.id]
            tgts = db.execute(
                select(FrTradeTarget).where(FrTradeTarget.trade_id == t.id).order_by(FrTradeTarget.seq)
            ).scalars().all()
            d["targets"] = [_target_row_to_dict(r, target_exit_prices.get(r.seq)) for r in tgts]
            out.append(d)
        return out


def get_trade(user_id: int, trade_id: int, mode: str | None = None) -> dict[str, Any] | None:
    with session_scope() as db:
        _mark_missing_entry_order_ids_failed(db, user_id)
        _sync_active_entry_order_statuses(db, user_id)
        normalized_mode = _normalize_mode_filter(mode)
        t = db.get(FrTrade, trade_id)
        if t is None or t.user_id != user_id:
            return None
        if normalized_mode and t.mode != normalized_mode:
            return None
        d = _trade_to_dict(t)
        target_exit_prices, sl_exit_option_price = _trade_exit_option_prices(db, t.id)
        d["sl_exit_option_price"] = sl_exit_option_price
        d["sl_hit"] = bool(
            sl_exit_option_price is not None
            or db.execute(
                select(FrTradeEvent.id)
                .where(FrTradeEvent.trade_id == t.id, FrTradeEvent.kind == "sl_hit")
                .limit(1)
            ).scalar()
        )
        display_phase = _phase_display_numbers(db, user_id, normalized_mode)
        if t.id in display_phase:
            d["phase_group"] = _display_phase_group(user_id, t.underlying, t.created_at, t.mode)
            d["phase_no"] = display_phase[t.id]
        tgts = db.execute(
            select(FrTradeTarget).where(FrTradeTarget.trade_id == t.id).order_by(FrTradeTarget.seq)
        ).scalars().all()
        d["targets"] = [_target_row_to_dict(r, target_exit_prices.get(r.seq)) for r in tgts]
        events = db.execute(
            select(FrTradeEvent).where(FrTradeEvent.trade_id == t.id).order_by(FrTradeEvent.ts.desc()).limit(100)
        ).scalars().all()
        d["events"] = [_event_to_dict(e) for e in events]
        return d


def list_phases(user_id: int, underlying: str | None = None, mode: str | None = None) -> list[dict[str, Any]]:
    """Phase history grouped by (underlying, session). Each entry is one
    position (phase) with its lifecycle summary: entry/exit, P&L, duration,
    achieved targets, and how it closed."""
    with session_scope() as db:
        _mark_missing_entry_order_ids_failed(db, user_id)
        _sync_active_entry_order_statuses(db, user_id)
        normalized_mode = _normalize_mode_filter(mode)
        q = select(FrTrade).where(FrTrade.user_id == user_id, FrTrade.phase_no > 0)
        if normalized_mode:
            q = q.where(FrTrade.mode == normalized_mode)
        if underlying:
            q = q.where(FrTrade.underlying == underlying.strip().upper())
        q = q.order_by(FrTrade.underlying, FrTrade.created_at, FrTrade.id)
        trades = db.execute(q).scalars().all()
        out: list[dict[str, Any]] = []
        display_phase = _phase_display_numbers(db, user_id, normalized_mode)
        for t in trades:
            target_exit_prices, sl_exit_option_price = _trade_exit_option_prices(db, t.id)
            tgts = db.execute(
                select(FrTradeTarget).where(FrTradeTarget.trade_id == t.id).order_by(FrTradeTarget.seq)
            ).scalars().all()
            achieved = [r.seq for r in tgts if r.status == "hit"]
            # How it closed: read the terminal event kind.
            terminal = db.execute(
                select(FrTradeEvent.kind).where(
                    FrTradeEvent.trade_id == t.id,
                    FrTradeEvent.kind.in_(("sl_hit", "completed", "emergency_exit", "broker_reconciled")),
                ).order_by(FrTradeEvent.ts.desc()).limit(1)
            ).scalar()
            exit_kind = (
                "auto" if terminal in ("sl_hit",) else
                "manual" if terminal in ("completed", "emergency_exit", "broker_reconciled") else
                ("open" if t.status in ("active", "draft") else "auto")
            )
            out.append({
                "trade_id": t.id,
                "mode": t.mode,
                "underlying": t.underlying,
                "phase_group": _display_phase_group(user_id, t.underlying, t.created_at, t.mode),
                "phase_no": display_phase.get(t.id, t.phase_no),
                "status": t.status,
                "option_symbol": t.option_symbol,
                "option_exchange": t.option_exchange,
                "side": t.side,
                "option_type": t.option_type,
                "lots": t.lots,
                "lot_size": t.lot_size,
                "total_qty": t.total_qty,
                "entry_time": t.created_at.isoformat() if t.created_at else None,
                "exit_time": t.closed_at.isoformat() if t.closed_at else None,
                "entry_futures_price": t.entry_futures_price,
                "entry_option_price": t.entry_option_price,
                "sl_price": t.sl_price,
                "sl_basis": t.sl_basis,
                "sl_exit_option_price": sl_exit_option_price,
                "sl_hit": bool(
                    sl_exit_option_price is not None
                    or terminal == "sl_hit"
                ),
                "targets_total": len(tgts),
                "targets_achieved": achieved,
                "targets": [_target_row_to_dict(r, target_exit_prices.get(r.seq)) for r in tgts],
                "realized_pnl": t.realized_pnl,
                "remaining_qty": t.remaining_qty,
                "pnl_qty": _pnl_quantity(t, int(t.remaining_qty or 0)),
                "duration_sec": (
                    int(((t.closed_at or t.updated_at) - t.created_at).total_seconds())
                    if t.created_at and (t.closed_at or t.updated_at) else None
                ),
                "exit_kind": exit_kind,
            })
        return out


_EXIT_STALE_AFTER = timedelta(seconds=60)


def _exit_state(t: FrTrade) -> str:
    return str(t.exit_state or "idle").lower()


def _claim_exit_attempt(
    trade_id: int,
    *,
    user_id: int | None,
    reason: str,
) -> tuple[FrTrade, str]:
    """Atomically reserve one trade for exactly one broker submission."""
    attempt_id = str(uuid.uuid4())
    now = datetime.now(tz=timezone.utc)
    stale_message: str | None = None
    claimed_trade: FrTrade | None = None
    with session_scope() as db:
        t = db.execute(
            select(FrTrade).where(FrTrade.id == trade_id).with_for_update()
        ).scalar_one_or_none()
        if t is None or (user_id is not None and t.user_id != user_id):
            raise FrError("Trade not found", 404)
        if t.status != "active":
            raise FrError(f"Trade is {t.status}, not active", 409)
        if int(t.remaining_qty or 0) <= 0:
            raise FrError("Trade has no remaining quantity", 409)
        state = _exit_state(t)
        if state == "blocked":
            detail = t.exit_block_reason or "a previous exit could not be safely confirmed"
            raise FrError(f"Exit protection is blocked: {detail}. Reconcile with the broker before retrying.", 409)
        if state in {"retry_wait", "retry_exhausted"}:
            raise FrError("A confirmed non-executed exit is waiting for its safe retry window", 409)
        if state == "submitting":
            attempted = t.exit_attempted_at
            if attempted is not None and attempted.tzinfo is None:
                attempted = attempted.replace(tzinfo=timezone.utc)
            if attempted is not None and now - attempted <= _EXIT_STALE_AFTER:
                raise FrError("An exit order is already being processed for this trade", 409)
            # A process may have died after sending the previous order.  Never
            # guess that it was not submitted; require broker reconciliation.
            t.exit_state = "blocked"
            t.exit_failure_count = int(t.exit_failure_count or 0) + 1
            t.exit_block_reason = "A previous exit attempt was interrupted before its broker result was confirmed"
            log_event(
                db,
                trade_id=t.id,
                user_id=t.user_id,
                kind="exit_blocked",
                severity="error",
                message=t.exit_block_reason,
                payload={"previous_attempt_id": t.exit_attempt_id},
            )
            stale_message = t.exit_block_reason
        else:
            t.exit_state = "submitting"
            t.exit_attempt_id = attempt_id
            t.exit_attempt_reason = reason
            t.exit_attempted_at = now
            t.exit_block_reason = None
            claimed_trade = t
    if stale_message:
        raise FrError(f"Exit protection is blocked: {stale_message}", 409)
    assert claimed_trade is not None
    return claimed_trade, attempt_id


def _set_exit_blocked(
    trade_id: int,
    attempt_id: str,
    message: str,
    *,
    order_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    with session_scope() as db:
        t = db.execute(
            select(FrTrade).where(FrTrade.id == trade_id).with_for_update()
        ).scalar_one_or_none()
        if t is None or t.exit_attempt_id != attempt_id:
            return
        t.exit_state = "blocked"
        t.exit_failure_count = int(t.exit_failure_count or 0) + 1
        t.exit_block_reason = message[:2000]
        if order_id:
            t.last_exit_order_id = order_id
        event_payload = {"attempt_id": attempt_id, "exit_order_id": order_id}
        if payload:
            event_payload.update(payload)
        log_event(
            db,
            trade_id=t.id,
            user_id=t.user_id,
            kind="exit_blocked",
            severity="error",
            message=f"Automatic exits paused after one failed attempt: {message}",
            payload=event_payload,
        )


def _set_exit_retry_wait(
    trade_id: int,
    attempt_id: str,
    message: str,
    *,
    order_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Persist a broker-confirmed non-execution without losing RL recovery.

    ``blocked`` is reserved for ambiguous submissions where retrying could
    duplicate a fill.  ``retry_wait`` means the broker positively rejected the
    request (or no request was sent), so a bounded retry is safe after position
    verification.
    """
    with session_scope() as db:
        t = db.execute(
            select(FrTrade).where(FrTrade.id == trade_id).with_for_update()
        ).scalar_one_or_none()
        if t is None or t.exit_attempt_id != attempt_id:
            return
        t.exit_state = "retry_wait"
        t.exit_failure_count = int(t.exit_failure_count or 0) + 1
        t.exit_block_reason = message[:2000]
        if order_id:
            t.last_exit_order_id = order_id
        event_payload = {"attempt_id": attempt_id, "exit_order_id": order_id}
        if payload:
            event_payload.update(payload)
        log_event(
            db,
            trade_id=t.id,
            user_id=t.user_id,
            kind="exit_retry_wait",
            severity="warning",
            message=f"Exit was not executed; safe retry is waiting: {message}",
            payload=event_payload,
        )


def _confirmed_non_execution(
    *,
    order_id: str | None,
    failure_message: str,
    broker_http_status: int | None,
) -> bool:
    """Return True only when retrying cannot duplicate a broker fill."""
    message = str(failure_message or "").lower()
    if order_id and any(
        marker in message
        for marker in (" was rejected", " was cancelled", " was canceled", " was failed")
    ):
        return True
    # A request rejected before an order id exists was not accepted by the
    # broker. Authentication and rate-limit failures are safe to retry too,
    # once their external condition has recovered.
    return not order_id and int(broker_http_status or 0) in {
        400, 401, 403, 404, 409, 422, 429,
    }


def _defer_exit_retry(trade_id: int, message: str) -> None:
    """Move the retry window forward after a failed verification call."""
    with session_scope() as db:
        t = db.get(FrTrade, trade_id)
        if t is None or _exit_state(t) != "retry_wait":
            return
        t.exit_attempted_at = datetime.now(tz=timezone.utc)
        t.exit_block_reason = message[:2000]


def prepare_automatic_exit(
    trade_id: int,
    *,
    reason: str,
    ctx: dict[str, Any] | None,
) -> bool:
    """Make a non-idle automatic exit eligible without risking duplication.

    A different, higher-priority RL reason may immediately supersede a target
    attempt that was positively rejected. Ambiguous ``blocked`` submissions
    remain blocked unless their broker order is now confirmed rejected.
    """
    with session_scope() as db:
        t = db.get(FrTrade, trade_id)
        if t is None or t.status != "active":
            return False
        state = _exit_state(t)
        if state == "idle":
            return True
        if state == "submitting":
            return False
        mode = t.mode
        user_id = t.user_id
        previous_reason = str(t.exit_attempt_reason or "")
        failures = int(t.exit_failure_count or 0)
        attempted_at = t.exit_attempted_at
        last_order_id = t.last_exit_order_id
        trade = t

    broker_ctx = ctx
    if state == "blocked":
        # Compatibility recovery for trades blocked by the first safety
        # release: only a broker-confirmed rejected/cancelled order is safe to
        # resume automatically.
        if mode == "sandbox" or not last_order_id:
            return False
        broker_ctx = broker_ctx or load_broker_context_sync(user_id)
        if broker_ctx is None:
            return False
        status, _, _ = _broker_order_status(
            last_order_id,
            broker_ctx["auth_token"],
            broker_ctx["broker"],
            broker_ctx.get("config"),
        )
        if status not in _ENTRY_FAILURE_STATUSES:
            return False

    # RL and explicit operator exits may supersede a lower-priority confirmed
    # non-execution. They still pass through a fresh broker-position check.
    priority_changed = (
        reason in {"sl", "manual", "emergency"}
        and reason != previous_reason
    )
    if state == "retry_exhausted" and not priority_changed:
        return False
    if state == "retry_wait" and not priority_changed:
        try:
            cooldown = max(1.0, float(get_config_value("exit_retry_cooldown_sec", "10")))
        except (TypeError, ValueError):
            cooldown = 10.0
        attempted = attempted_at
        if attempted is not None and attempted.tzinfo is None:
            attempted = attempted.replace(tzinfo=timezone.utc)
        if attempted is not None and datetime.now(tz=timezone.utc) - attempted < timedelta(seconds=cooldown):
            return False
        try:
            max_attempts = max(1, int(float(get_config_value("exit_retry_max_attempts", "3"))))
        except (TypeError, ValueError):
            max_attempts = 3
        if failures >= max_attempts:
            with session_scope() as db:
                current = db.get(FrTrade, trade_id)
                if current is not None and _exit_state(current) == "retry_wait":
                    # Keep this distinct from an ambiguous broker submission.
                    # The same trigger is exhausted, while a later risk-limit
                    # trigger may still safely supersede it after verification.
                    current.exit_state = "retry_exhausted"
                    current.exit_block_reason = (
                        f"{current.exit_block_reason or 'Exit was rejected'}; "
                        f"automatic retry limit ({max_attempts}) reached"
                    )[:2000]
                    log_event(
                        db,
                        trade_id=current.id,
                        user_id=current.user_id,
                        kind="exit_retry_limit",
                        severity="error",
                        message=current.exit_block_reason,
                        payload={"reason": reason, "failure_count": failures},
                    )
            return False

    if mode == "sandbox":
        with session_scope() as db:
            current = db.get(FrTrade, trade_id)
            if current is None or current.status != "active":
                return False
            current.exit_state = "idle"
            current.exit_attempt_id = None
            current.exit_attempt_reason = None
            current.exit_block_reason = None
            if priority_changed:
                current.exit_failure_count = 0
        return True

    broker_ctx = broker_ctx or load_broker_context_sync(user_id)
    if broker_ctx is None:
        _defer_exit_retry(trade_id, "No active broker session")
        return False
    snapshot = get_position_snapshot(trade, broker_ctx, force=True)
    if not snapshot.supported or not snapshot.ok:
        _defer_exit_retry(
            trade_id,
            snapshot.message or "Broker position could not be verified before retry",
        )
        return False
    action, _, message = _apply_position_snapshot(
        trade_id,
        snapshot,
        clear_block=True,
    )
    if action in {"closed", "blocked", "error"} or message:
        return False
    if priority_changed:
        with session_scope() as db:
            current = db.get(FrTrade, trade_id)
            if current is not None and current.status == "active":
                current.exit_failure_count = 0
    return True


def _apply_position_snapshot(
    trade_id: int,
    snapshot: PositionSnapshot,
    *,
    attempt_id: str | None = None,
    clear_block: bool = False,
) -> tuple[str, int, str | None]:
    """Persist a trusted broker quantity.

    Returns ``(action, remaining, message)`` where action is unchanged,
    adjusted, closed, blocked, or error.
    """
    if not snapshot.ok:
        return "error", -1, snapshot.message or "Broker positions could not be verified"
    if not snapshot.supported:
        return "unchanged", -1, None
    assert snapshot.quantity is not None
    with session_scope() as db:
        t = db.execute(
            select(FrTrade).where(FrTrade.id == trade_id).with_for_update()
        ).scalar_one_or_none()
        if t is None:
            return "error", -1, "Trade not found"
        if attempt_id is not None and t.exit_attempt_id != attempt_id:
            return "error", int(t.remaining_qty or 0), "Exit attempt ownership changed"
        if t.status != "active":
            return "closed", int(t.remaining_qty or 0), None

        signed_qty = int(snapshot.quantity)
        decision = decide_position_reconciliation(t.remaining_qty, t.side, signed_qty)
        broker_qty = decision.broker_quantity
        t.broker_remaining_qty = broker_qty
        t.broker_reconciled_at = datetime.now(tz=timezone.utc)

        if decision.action == "closed":
            old_remaining = int(t.remaining_qty or 0)
            t.remaining_qty = 0
            t.status = "completed"
            t.closed_at = datetime.now(tz=timezone.utc)
            t.exit_state = "idle"
            t.exit_attempt_id = None
            t.exit_attempt_reason = None
            t.exit_block_reason = None
            pending = db.execute(
                select(FrTradeTarget).where(
                    FrTradeTarget.trade_id == t.id,
                    FrTradeTarget.status == "pending",
                )
            ).scalars().all()
            for target in pending:
                target.status = "skipped"
            log_event(
                db,
                trade_id=t.id,
                user_id=t.user_id,
                kind="broker_reconciled",
                severity="warning",
                message=(
                    f"Broker position is zero; OpenBull closed the trade without placing another order "
                    f"({old_remaining} recorded qty reconciled)"
                ),
                payload={
                    "old_remaining_qty": old_remaining,
                    "broker_remaining_qty": 0,
                    "broker_pnl": snapshot.broker_pnl,
                },
            )
            return "closed", 0, None

        recorded = int(t.remaining_qty or 0)
        if decision.action == "blocked":
            message = decision.message or "Broker position conflicts with the OpenBull trade"
            t.exit_state = "blocked"
            t.exit_failure_count = int(t.exit_failure_count or 0) + 1
            t.exit_block_reason = message
            log_event(
                db, trade_id=t.id, user_id=t.user_id, kind="exit_blocked", severity="error",
                message=message,
                payload={
                    "broker_signed_qty": signed_qty,
                    "broker_remaining_qty": broker_qty,
                    "recorded_remaining_qty": recorded,
                },
            )
            return "blocked", recorded, message

        action = decision.action
        if action == "adjusted":
            t.remaining_qty = broker_qty
            action = "adjusted"
            log_event(
                db,
                trade_id=t.id,
                user_id=t.user_id,
                kind="broker_reconciled",
                severity="warning",
                message=f"OpenBull remaining quantity reconciled from {recorded} to broker quantity {broker_qty}",
                payload={
                    "old_remaining_qty": recorded,
                    "broker_remaining_qty": broker_qty,
                    "broker_pnl": snapshot.broker_pnl,
                },
            )
        if clear_block:
            t.exit_state = "idle"
            t.exit_attempt_id = None
            t.exit_attempt_reason = None
            t.exit_block_reason = None
            log_event(
                db,
                trade_id=t.id,
                user_id=t.user_id,
                kind="exit_resumed",
                message=f"Exit protection resumed after broker verification ({broker_qty} qty open)",
                payload={"broker_remaining_qty": broker_qty},
            )
        return action, broker_qty, None


def reconcile_trade(
    user_id: int,
    trade_id: int,
    *,
    ctx: dict[str, Any] | None = None,
    force: bool = True,
    resume: bool = False,
) -> dict[str, Any]:
    """Synchronise one active live trade with the broker position book."""
    stale_attempt_id: str | None = None
    with session_scope() as db:
        t = db.get(FrTrade, trade_id)
        if t is None or t.user_id != user_id:
            raise FrError("Trade not found", 404)
        if t.mode == "sandbox":
            if resume:
                t.exit_state = "idle"
                t.exit_attempt_id = None
                t.exit_attempt_reason = None
                t.exit_block_reason = None
            return get_trade(user_id, trade_id) or {}
        if t.status != "active":
            return get_trade(user_id, trade_id) or {}
        if _exit_state(t) == "submitting" and not resume:
            attempted = t.exit_attempted_at
            if attempted is not None and attempted.tzinfo is None:
                attempted = attempted.replace(tzinfo=timezone.utc)
            if attempted is not None and datetime.now(tz=timezone.utc) - attempted <= _EXIT_STALE_AFTER:
                return get_trade(user_id, trade_id) or {}
            stale_attempt_id = t.exit_attempt_id
        trade = t
    broker_ctx = ctx or load_broker_context_sync(user_id)
    snapshot = get_position_snapshot(trade, broker_ctx, force=force)
    if not snapshot.supported:
        if resume:
            raise FrError("Safe broker reconciliation is not supported for this broker", 409)
        return get_trade(user_id, trade_id) or {}
    if not snapshot.ok:
        if stale_attempt_id:
            _set_exit_blocked(
                trade_id,
                stale_attempt_id,
                f"Interrupted exit could not be reconciled: {snapshot.message}",
            )
        raise FrError(f"Broker position could not be verified: {snapshot.message}", 503)
    action, _, message = _apply_position_snapshot(
        trade_id,
        snapshot,
        attempt_id=stale_attempt_id,
        clear_block=resume,
    )
    if stale_attempt_id and action != "closed":
        _set_exit_blocked(
            trade_id,
            stale_attempt_id,
            "A previous exit was interrupted; broker quantity was checked and explicit operator resume is required",
        )
    if action == "blocked" or message:
        raise FrError(message or "Broker reconciliation blocked the trade", 409)
    return get_trade(user_id, trade_id) or {}


def execute_trade_exit(
    trade_id: int,
    *,
    user_id: int | None,
    requested_qty: int | None,
    reason: str,
    ctx: dict[str, Any] | None = None,
    futures_price: float | None = None,
    target_seq: int | None = None,
) -> ExitExecutionResult:
    """Single safe order path for automatic and user-initiated exits."""
    trade, attempt_id = _claim_exit_attempt(trade_id, user_id=user_id, reason=reason)
    broker_ctx = ctx
    if trade.mode != "sandbox":
        broker_ctx = broker_ctx or load_broker_context_sync(trade.user_id)
        if broker_ctx is None:
            message = "No active broker session"
            _set_exit_retry_wait(
                trade_id,
                attempt_id,
                message,
                payload={"reason": reason, "futures_price": futures_price},
            )
            return ExitExecutionResult(False, message, retryable=True)
        snapshot = get_position_snapshot(trade, broker_ctx, force=True)
        if snapshot.supported:
            if not snapshot.ok:
                message = f"Broker position could not be verified: {snapshot.message}"
                # No order has been submitted yet, so a later verified retry
                # cannot duplicate a fill.
                _set_exit_retry_wait(
                    trade_id,
                    attempt_id,
                    message,
                    payload={"reason": reason, "futures_price": futures_price},
                )
                return ExitExecutionResult(False, message, retryable=True)
            action, reconciled_qty, message = _apply_position_snapshot(
                trade_id, snapshot, attempt_id=attempt_id
            )
            if action == "closed":
                return ExitExecutionResult(
                    True,
                    "Broker position was already closed; OpenBull was reconciled without a new order",
                    remaining_qty=0,
                    reconciled=True,
                )
            if action in {"blocked", "error"}:
                if action == "error":
                    _set_exit_retry_wait(
                        trade_id,
                        attempt_id,
                        message or "Broker reconciliation failed before order submission",
                        payload={"reason": reason, "futures_price": futures_price},
                    )
                return ExitExecutionResult(
                    False,
                    message or "Broker reconciliation blocked the exit",
                    remaining_qty=max(0, reconciled_qty),
                    blocked=action == "blocked",
                    retryable=action == "error",
                )

    with session_scope() as db:
        current = db.get(FrTrade, trade_id)
        if current is None or current.status != "active" or current.exit_attempt_id != attempt_id:
            return ExitExecutionResult(False, "Trade changed while the exit was being prepared", blocked=True)
        remaining = int(current.remaining_qty or 0)
        qty = remaining if requested_qty is None else min(max(0, int(requested_qty)), remaining)
        if qty <= 0:
            current.exit_state = "idle"
            current.exit_attempt_id = None
            current.exit_attempt_reason = None
            return ExitExecutionResult(True, "Nothing to exit", remaining_qty=remaining)
        order_data = {
            "symbol": current.option_symbol,
            "exchange": current.option_exchange,
            "action": "SELL" if current.side == "BUY" else "BUY",
            "quantity": str(qty),
            "pricetype": "MARKET",
            "product": current.product,
            "price": "0",
            "trigger_price": "0",
            "strategy": f"FuturesRisk-{reason}",
        }

    ok, resp, status_code = dispatch_order(
        trade.mode,
        trade.user_id,
        order_data,
        auth_token=broker_ctx["auth_token"] if broker_ctx else None,
        broker=broker_ctx["broker"] if broker_ctx else None,
        config=broker_ctx.get("config") if broker_ctx else None,
    )
    order_id = str(resp.get("orderid")) if isinstance(resp, dict) and resp.get("orderid") else None
    fill_price = _extract_order_fill_price(resp) if isinstance(resp, dict) else None
    failure_message: str | None = None
    if not ok:
        failure_message = resp.get("message", "Exit order failed") if isinstance(resp, dict) else "Exit order failed"
    elif trade.mode != "sandbox":
        if not order_id:
            failure_message = "Broker did not return an exit order id"
        else:
            confirmed, confirm_message, confirmed_price = _confirm_entry_order(
                order_id,
                broker_ctx["auth_token"],
                broker_ctx["broker"],
                broker_ctx.get("config"),
            )
            fill_price = confirmed_price or fill_price
            if not confirmed:
                failure_message = confirm_message or "Broker exit order was not completed"

    if failure_message:
        # A rejection such as Dhan DH-1111 often means the position was closed
        # directly at the broker.  Verify once, then either reconcile to zero
        # or open the persistent circuit breaker.  Never submit a second order.
        if broker_ctx and trade.mode != "sandbox":
            invalidate_position_cache(broker_ctx["broker"], broker_ctx["auth_token"])
            after = get_position_snapshot(trade, broker_ctx, force=True)
            if after.supported and after.ok:
                action, remaining_after, reconcile_message = _apply_position_snapshot(
                    trade_id, after, attempt_id=attempt_id
                )
                if action == "closed":
                    return ExitExecutionResult(
                        True,
                        "Broker position is zero; OpenBull reconciled the external close",
                        order_id=order_id,
                        remaining_qty=0,
                        reconciled=True,
                    )
                if reconcile_message:
                    failure_message = f"{failure_message}; {reconcile_message}"
        retryable = _confirmed_non_execution(
            order_id=order_id,
            failure_message=failure_message,
            broker_http_status=status_code,
        )
        state_writer = _set_exit_retry_wait if retryable else _set_exit_blocked
        state_writer(
            trade_id,
            attempt_id,
            failure_message,
            order_id=order_id,
            payload={"broker_http_status": status_code, "reason": reason, "futures_price": futures_price},
        )
        return ExitExecutionResult(
            False,
            failure_message,
            order_id=order_id,
            remaining_qty=remaining,
            fill_price=fill_price,
            blocked=not retryable,
            retryable=retryable,
        )

    if broker_ctx and trade.mode != "sandbox":
        invalidate_position_cache(broker_ctx["broker"], broker_ctx["auth_token"])

    with session_scope() as db:
        t = db.execute(
            select(FrTrade).where(FrTrade.id == trade_id).with_for_update()
        ).scalar_one_or_none()
        if t is None or t.exit_attempt_id != attempt_id:
            # Do not overwrite a newer attempt owner.  Its reconciliation pass
            # will see the broker quantity change before any submission.
            return ExitExecutionResult(False, "Exit requires broker reconciliation", order_id=order_id, blocked=True)
        exit_px = fill_price or _option_exit_price(t.option_symbol, t.option_exchange, fallback=t.entry_option_price)
        pnl_inc = _trade_exit_pnl(t, exit_px, qty)
        t.remaining_qty = max(0, int(t.remaining_qty or 0) - qty)
        t.realized_pnl = round(float(t.realized_pnl or 0.0) + pnl_inc, 2)
        t.last_exit_order_id = order_id
        t.exit_state = "idle"
        t.exit_attempt_id = None
        t.exit_attempt_reason = None
        t.exit_block_reason = None
        t.exit_failure_count = 0
        t.modified_by = user_id or t.modified_by

        if target_seq is not None:
            target = db.execute(
                select(FrTradeTarget).where(
                    FrTradeTarget.trade_id == t.id,
                    FrTradeTarget.seq == target_seq,
                )
            ).scalar_one_or_none()
            if target is not None:
                target.status = "hit"
                target.hit_futures_price = futures_price
                target.exit_order_id = order_id
                target.hit_at = datetime.now(tz=timezone.utc)

        closed = t.remaining_qty <= 0
        if reason == "sl":
            t.status = "stopped"
            t.closed_at = datetime.now(tz=timezone.utc)
            kind, severity = "sl_hit", "warning"
            message = (
                f"Stop-loss hit at futures {futures_price} (SL {t.sl_price}, basis {t.sl_basis}); "
                f"exited {qty} @ ~{exit_px} (P&L {pnl_inc:+.2f})"
            )
        elif target_seq is not None:
            if closed:
                t.status = "completed"
                t.closed_at = datetime.now(tz=timezone.utc)
            kind, severity = "target_hit", "info"
            message = (
                f"Target {target_seq} hit at futures {futures_price}; exited {qty} @ ~{exit_px} "
                f"(P&L {pnl_inc:+.2f})"
            )
        elif reason == "emergency":
            if closed:
                t.status = "completed"
                t.closed_at = datetime.now(tz=timezone.utc)
            kind, severity = "emergency_exit", "warning"
            message = f"EMERGENCY exit of {qty} qty {t.option_symbol} @ ~{exit_px} (P&L {pnl_inc:+.2f})"
        elif closed:
            t.status = "completed"
            t.closed_at = datetime.now(tz=timezone.utc)
            kind, severity = "completed", "info"
            message = f"Manual full exit of {qty} qty {t.option_symbol} @ ~{exit_px} (P&L {pnl_inc:+.2f})"
        else:
            kind, severity = "partial_exit", "info"
            message = (
                f"Manual partial exit of {qty} qty {t.option_symbol} @ ~{exit_px} "
                f"(P&L {pnl_inc:+.2f}; {t.remaining_qty} left)"
            )
        log_event(
            db,
            trade_id=t.id,
            user_id=t.user_id,
            kind=kind,
            severity=severity,
            message=message,
            payload={
                "attempt_id": attempt_id,
                "exit_order_id": order_id,
                "qty": qty,
                "remaining": t.remaining_qty,
                "futures_price": futures_price,
                "exit_option_price": exit_px,
                "pnl": pnl_inc,
                "target_seq": target_seq,
            },
        )
        return ExitExecutionResult(
            True,
            message,
            order_id=order_id,
            exited_qty=qty,
            remaining_qty=int(t.remaining_qty or 0),
            fill_price=exit_px,
            pnl=pnl_inc,
        )


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
        remaining = int(t.remaining_qty or 0)

    if emergency or qty is None:
        exit_qty = remaining
    else:
        exit_qty = max(0, min(int(qty), remaining))
        if exit_qty == 0:
            raise FrError("qty must be between 1 and the remaining quantity", 400)

    reason = "emergency" if emergency else "manual"
    if not prepare_automatic_exit(trade_id, reason=reason, ctx=None):
        raise FrError(
            "Exit protection is waiting for broker verification; use Verify broker & resume if it remains paused",
            409,
        )

    result = execute_trade_exit(
        trade_id,
        user_id=user_id,
        requested_qty=exit_qty,
        reason=reason,
    )
    if not result.ok:
        raise FrError(result.message, 409 if result.blocked else 502)
    return get_trade(user_id, trade_id) or {}


# ---------------------------------------------------------------------------
# Modify (draft or active) + delete
# ---------------------------------------------------------------------------

# Fields that may only be changed while a position is a draft (pre-placement).
_DRAFT_ONLY_FIELDS = {"underlying", "underlying_exchange", "option_type", "side", "expiry", "strike", "offset", "lots", "product"}
# Fields editable at any time, including after placement.
_LIVE_EDITABLE_FIELDS = {"sl_points", "targets", "target_template_id", "trailing_mode"}


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

            target_source = None
            if "targets" in fields and fields["targets"] is not None:
                target_source = _normalise_target_exit_pcts([
                    {"seq": i + 1, "points": float(x["points"]), "exit_pct": float(x.get("exit_pct", 0))}
                    for i, x in enumerate(fields["targets"])
                    if float(x.get("points", 0)) > 0
                ])
            elif fields.get("target_template_id") is not None:
                target_source = _normalise_target_exit_pcts(list_targets(enabled_only=True, template_id=int(fields["target_template_id"])))

            if target_source is not None:
                # Replace only the PENDING targets; keep already-hit ones intact.
                hit = db.execute(
                    select(FrTradeTarget).where(
                        FrTradeTarget.trade_id == trade_id, FrTradeTarget.status == "hit"
                    ).order_by(FrTradeTarget.seq)
                ).scalars().all()
                hit_lots = sum(int(r.exit_qty) for r in hit) // max(1, t.lot_size)
                remaining_lots = max(0, t.lots - hit_lots)
                base_seq = len(hit)
                template = _normalise_target_exit_pcts([
                    {"seq": base_seq + i + 1, "points": float(x["points"]), "exit_pct": float(x.get("exit_pct", 0))}
                    for i, x in enumerate(target_source)
                    if float(x.get("points", 0)) > 0
                ])
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
            if fields.get("target_template_id") is not None:
                meta = dict(t.meta or {})
                params = dict(meta.get("params") or {})
                params["target_template_id"] = int(fields["target_template_id"])
                meta["params"] = params
                t.meta = meta
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
