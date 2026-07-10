"""Shared strike-selection values and resolution for Futures-Risk clients."""

from __future__ import annotations

from enum import Enum
import re
from typing import Any

from backend.services.option_symbol_service import _apply_offset


class StrikeSelectionMethod(str, Enum):
    ATM = "ATM"
    ITM_OTM = "ITM_OTM"
    MANUAL = "MANUAL"
    OFFSET = "OFFSET"


class MoneynessSelection(str, Enum):
    ATM = "ATM"
    ITM1 = "ITM1"
    ITM2 = "ITM2"
    ITM3 = "ITM3"
    ITM4 = "ITM4"
    ITM5 = "ITM5"
    ITM6 = "ITM6"
    ITM7 = "ITM7"
    ITM8 = "ITM8"
    ITM9 = "ITM9"
    ITM10 = "ITM10"
    OTM1 = "OTM1"
    OTM2 = "OTM2"
    OTM3 = "OTM3"
    OTM4 = "OTM4"
    OTM5 = "OTM5"
    OTM6 = "OTM6"
    OTM7 = "OTM7"
    OTM8 = "OTM8"
    OTM9 = "OTM9"
    OTM10 = "OTM10"


def normalize_method(value: Any, default: StrikeSelectionMethod = StrikeSelectionMethod.ATM) -> StrikeSelectionMethod:
    raw = (value.value if isinstance(value, StrikeSelectionMethod) else str(value or "")).strip().upper()
    raw = re.sub(r"[\s/\-]+", "_", raw)
    aliases = {
        "ITMOTM": StrikeSelectionMethod.ITM_OTM,
        "ITM_OTM": StrikeSelectionMethod.ITM_OTM,
        "MANUAL_STRIKE": StrikeSelectionMethod.MANUAL,
    }
    if raw in aliases:
        return aliases[raw]
    try:
        return StrikeSelectionMethod(raw)
    except ValueError:
        return default


def normalize_moneyness(value: Any) -> MoneynessSelection:
    raw = (value.value if isinstance(value, MoneynessSelection) else str(value or "ATM")).strip().upper().replace(" ", "")
    try:
        return MoneynessSelection(raw)
    except ValueError:
        return MoneynessSelection.ATM


def resolve_strike(
    *,
    method: StrikeSelectionMethod,
    option_type: str,
    strikes: list[float],
    atm: float | None,
    moneyness: MoneynessSelection = MoneynessSelection.ATM,
    manual_strike: float | None = None,
    offset_strike: float | None = None,
) -> float:
    """Resolve one CE/PE strike without changing order placement semantics."""
    if method == StrikeSelectionMethod.MANUAL:
        if manual_strike is None or manual_strike <= 0:
            raise ValueError("A positive manual strike is required")
        if strikes and not any(abs(float(s) - float(manual_strike)) < 0.0001 for s in strikes):
            raise ValueError(f"Manual strike {manual_strike:g} is not available for the selected expiry")
        return float(manual_strike)

    if atm is None or atm <= 0:
        raise ValueError("ATM strike is unavailable for the selected expiry")
    if method == StrikeSelectionMethod.OFFSET:
        if offset_strike is None or offset_strike <= 0:
            raise ValueError("Offset strike is unavailable for the selected expiry")
        return float(offset_strike)

    offset = "ATM" if method == StrikeSelectionMethod.ATM else normalize_moneyness(moneyness).value
    resolved = _apply_offset(float(atm), offset, option_type, strikes)
    if resolved is None:
        raise ValueError(f"Strike selection {offset} is outside the available strike range")
    return float(resolved)
