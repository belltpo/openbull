"""Exchange lot-size fallbacks for Futures-Risk P&L.

Broker master contracts remain the first source of truth. This table is used
when a broker/exchange reports quantity as lots, or when a stored symbol map is
missing a usable lot size.
"""

from __future__ import annotations


LOT_SIZE_BY_UNDERLYING: dict[str, int] = {
    "NIFTY": 65,
    "BANKNIFTY": 15,
    "CRUDEOIL": 100,
    "CRUDEOILM": 10,
    "NATURALGAS": 1250,
    "GOLD": 100,
    "GOLDM": 10,
    "SILVER": 30,
    "SILVERM": 5,
    "COPPER": 2500,
    "COPPERM": 250,
    "ALUMINIUM": 5000,
    "ALUMINI": 1000,
    "ZINC": 5000,
    "LEAD": 5000,
    # Existing supported variants retained so older symbol maps do not break.
    "NATGASMINI": 250,
    "SILVERMIC": 1,
    "SILVER100": 100,
    "GOLDPETAL": 1,
}


MCX_UNDERLYINGS: frozenset[str] = frozenset({
    "CRUDEOIL",
    "CRUDEOILM",
    "NATURALGAS",
    "NATGASMINI",
    "GOLD",
    "GOLDM",
    "GOLDPETAL",
    "SILVER",
    "SILVERM",
    "SILVERMIC",
    "SILVER100",
    "COPPER",
    "COPPERM",
    "ALUMINIUM",
    "ALUMINI",
    "ZINC",
    "LEAD",
})
