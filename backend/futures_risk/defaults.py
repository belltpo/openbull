"""Seed defaults for the Futures-Risk module config, target template, and
underlying→futures symbol map."""

from __future__ import annotations

# key -> (value, description, is_editable)
CONFIG_DEFAULTS: dict[str, tuple[str, str, bool]] = {
    "auto_exit_enabled": ("true", "Master switch for automatic target/SL exits", True),
    "default_sl_points": ("30", "Default stop-loss distance in futures points (pre-fills popup)", True),
    "default_lots": ("1", "Default lots pre-filled in the order popup", True),
    "default_underlying": ("", "Default underlying selected in the quick order popup", True),
    "contract_order_templates": ("{}", "Per-contract quick-order setup templates", True),
    "default_product": ("MIS", "Default product for new option trades (MIS/NRML)", True),
    "trailing_enabled": ("true", "Trail the stop-loss as targets are hit", True),
    "trailing_mode": (
        "entry_after_t1",
        "How SL trails: entry_after_t1 (cost-to-cost after T1) | prev_target | off",
        True,
    ),
    "poll_interval_sec": ("2", "Futures-price evaluation interval in seconds", True),
}

# (seq, points, exit_pct)
TARGET_DEFAULTS: list[tuple[int, float, float]] = [
    (1, 50.0, 25.0),
    (2, 100.0, 25.0),
    (3, 150.0, 25.0),
    (4, 200.0, 25.0),
]

# (underlying, underlying_exchange, futures_exchange, lot_size, auto_resolve)
SYMBOL_MAP_DEFAULTS: list[tuple[str, str, str, int, bool]] = [
    ("NIFTY", "NSE_INDEX", "NFO", 75, True),
    ("BANKNIFTY", "NSE_INDEX", "NFO", 35, True),
]
