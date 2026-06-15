"""
Futures-Risk Options module tables.

A lightweight options-trading module where the *trade* is in options but all
target / stop-loss / trailing risk is measured on the underlying FUTURES price.

Design mirrors the sandbox tables: plain ``Column`` declarations, ``user_id``
ownership, JSONB for flexible payloads, all in the same Postgres DB.

Tables
------
* ``fr_config``        — global admin key/value config (default SL, trailing, …)
* ``fr_target_level``  — admin-editable target template rows (CRUD)
* ``fr_symbol_map``    — underlying → futures-contract mapping (CRUD)
* ``fr_trade``         — one placed option trade + its futures-risk plan
* ``fr_trade_target``  — per-trade snapshot of each target level
* ``fr_trade_event``   — audit / auto-exit log per trade
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from backend.database import Base


class FrConfig(Base):
    """Global key/value config for the Futures-Risk module (admin-editable)."""

    __tablename__ = "fr_config"

    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)
    description = Column(String(500), nullable=True)
    is_editable = Column(Boolean, nullable=False, default=True)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class FrTargetLevel(Base):
    """Admin target template. Each row is one target (T1, T2 …). Snapshotted
    onto a trade at placement so later admin edits never change live trades."""

    __tablename__ = "fr_target_level"

    id = Column(Integer, primary_key=True)
    seq = Column(Integer, nullable=False)  # 1-based target index (T1=1, T2=2, …)
    points = Column(Float, nullable=False)  # futures points from entry
    exit_pct = Column(Float, nullable=False, default=0.0)  # % of position to exit
    enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (Index("idx_fr_target_seq", "seq", unique=True),)


class FrSymbolMap(Base):
    """Maps an option underlying to the futures contract whose price drives the
    target/SL triggers. ``auto_resolve`` picks the current-month FUT from the
    symtoken master at trade time; otherwise ``futures_symbol`` is used as-is."""

    __tablename__ = "fr_symbol_map"

    id = Column(Integer, primary_key=True)
    underlying = Column(String(50), unique=True, nullable=False, index=True)  # NIFTY, BANKNIFTY, RELIANCE
    underlying_exchange = Column(String(20), nullable=False, default="NSE_INDEX")
    futures_symbol = Column(String(100), nullable=True)  # explicit FUT symbol, or null when auto_resolve
    futures_exchange = Column(String(20), nullable=False, default="NFO")
    lot_size = Column(Integer, nullable=False, default=0)
    auto_resolve = Column(Boolean, nullable=False, default=True)  # resolve near-month FUT from symtoken
    enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class FrTrade(Base):
    """One placed option trade with a futures-based risk plan."""

    __tablename__ = "fr_trade"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    mode = Column(String(10), nullable=False, default="live")  # live | sandbox

    # --- option leg ---
    underlying = Column(String(50), nullable=False)
    option_symbol = Column(String(100), nullable=False)
    option_exchange = Column(String(20), nullable=False)
    option_type = Column(String(2), nullable=False)  # CE | PE
    side = Column(String(4), nullable=False)  # BUY | SELL (on the option)
    product = Column(String(10), nullable=False, default="MIS")
    expiry = Column(String(20), nullable=True)
    strike = Column(Float, nullable=True)
    lots = Column(Integer, nullable=False, default=1)
    lot_size = Column(Integer, nullable=False, default=1)
    total_qty = Column(Integer, nullable=False, default=0)
    remaining_qty = Column(Integer, nullable=False, default=0)

    entry_option_price = Column(Float, nullable=False, default=0.0)
    entry_order_id = Column(String(60), nullable=True)

    # --- futures reference ---
    futures_symbol = Column(String(100), nullable=False)
    futures_exchange = Column(String(20), nullable=False, default="NFO")
    entry_futures_price = Column(Float, nullable=False, default=0.0)
    # +1 = bullish (profit when futures rises): targets above, SL below
    # -1 = bearish (profit when futures falls): targets below, SL above
    direction = Column(Integer, nullable=False, default=1)

    # --- stop loss (dynamic; trails after targets) ---
    sl_points = Column(Float, nullable=False, default=0.0)
    sl_price = Column(Float, nullable=False, default=0.0)  # current SL trigger (futures price)
    sl_basis = Column(String(20), nullable=False, default="initial")  # initial | entry | target<n>

    # draft = created but not placed (fully editable, ignored by the engine)
    status = Column(String(12), nullable=False, default="active", index=True)  # draft | active | completed | stopped | cancelled | error
    realized_pnl = Column(Float, nullable=False, default=0.0)
    meta = Column(JSONB, nullable=True)

    # --- audit actors (who created / last modified this trade) ---
    created_by = Column(Integer, nullable=True)
    modified_by = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_fr_trade_user_status", "user_id", "status"),
        Index("idx_fr_trade_fut_status", "futures_symbol", "futures_exchange", "status"),
    )


class FrTradeTarget(Base):
    """Per-trade snapshot of one target level (frozen at placement)."""

    __tablename__ = "fr_trade_target"

    id = Column(Integer, primary_key=True)
    trade_id = Column(Integer, ForeignKey("fr_trade.id", ondelete="CASCADE"), nullable=False, index=True)
    seq = Column(Integer, nullable=False)  # 1-based
    points = Column(Float, nullable=False)
    exit_pct = Column(Float, nullable=False, default=0.0)
    trigger_price = Column(Float, nullable=False)  # futures price that fires this target
    exit_qty = Column(Integer, nullable=False, default=0)  # whole-lot quantity to exit
    status = Column(String(10), nullable=False, default="pending")  # pending | hit | skipped
    hit_futures_price = Column(Float, nullable=True)
    exit_order_id = Column(String(60), nullable=True)
    hit_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("idx_fr_tgt_trade_seq", "trade_id", "seq", unique=True),)


class FrTradeEvent(Base):
    """Audit trail / auto-exit log for a trade."""

    __tablename__ = "fr_trade_event"

    id = Column(Integer, primary_key=True)
    trade_id = Column(Integer, ForeignKey("fr_trade.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    ts = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # entry | target_hit | sl_hit | sl_trail | partial_exit | completed | error | info
    kind = Column(String(20), nullable=False)
    severity = Column(String(10), nullable=False, default="info")
    message = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=True)

    __table_args__ = (
        Index("idx_fr_event_trade_ts", "trade_id", "ts"),
        Index("idx_fr_event_user_ts", "user_id", "ts"),
    )
