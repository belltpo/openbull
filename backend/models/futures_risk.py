"""
Futures-Risk Options module tables.

A lightweight options-trading module where the *trade* is in options but all
target / stop-loss / trailing risk is measured on the underlying FUTURES price.

Design mirrors the sandbox tables: plain ``Column`` declarations, ``user_id``
ownership, JSONB for flexible payloads, all in the same Postgres DB.

Tables
------
* ``fr_config``        — global admin key/value config (default SL, trailing, …)
* ``fr_target_template`` — named target templates (CRUD)
* ``fr_target_level``  — target rows within each template (CRUD)
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


class FrTargetTemplate(Base):
    """Named target template. Target rows are snapshotted onto a trade at
    placement so later template edits never change live trades."""

    __tablename__ = "fr_target_template"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(500), nullable=True)
    is_default = Column(Boolean, nullable=False, default=False)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (Index("idx_fr_target_template_default", "is_default"),)


class FrTargetLevel(Base):
    """One target row (T1, T2 …) inside a named template."""

    __tablename__ = "fr_target_level"

    id = Column(Integer, primary_key=True)
    template_id = Column(
        Integer,
        ForeignKey("fr_target_template.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq = Column(Integer, nullable=False)  # 1-based target index (T1=1, T2=2, …)
    points = Column(Float, nullable=False)  # futures points from entry
    exit_pct = Column(Float, nullable=False, default=0.0)  # % of position to exit
    enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (Index("idx_fr_target_template_seq", "template_id", "seq", unique=True),)


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

    # --- broker exit safety ---
    # A persistent state is required because auto-exit runs in a background
    # thread while manual/emergency exits arrive through HTTP.  It prevents
    # both paths (and process restarts) from blindly submitting duplicate
    # orders after a rejection or an uncertain broker response.
    exit_state = Column(String(20), nullable=False, default="idle")
    exit_attempt_id = Column(String(36), nullable=True)
    exit_attempt_reason = Column(String(20), nullable=True)
    exit_attempted_at = Column(DateTime(timezone=True), nullable=True)
    exit_failure_count = Column(Integer, nullable=False, default=0)
    exit_block_reason = Column(Text, nullable=True)
    last_exit_order_id = Column(String(60), nullable=True)
    broker_remaining_qty = Column(Integer, nullable=True)
    broker_reconciled_at = Column(DateTime(timezone=True), nullable=True)

    # --- audit actors (who created / last modified this trade) ---
    created_by = Column(Integer, nullable=True)
    modified_by = Column(Integer, nullable=True)

    # --- phase tracking (sequential positions on the same mode+underlying+session) ---
    # phase_group = "{user_id}:{mode}:{underlying}:{session_date}"; phase_no increments
    # 1,2,3… as each position closes and a new one opens within that group.
    phase_group = Column(String(120), nullable=True, index=True)
    phase_no = Column(Integer, nullable=False, default=0)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_fr_trade_user_status", "user_id", "status"),
        Index("idx_fr_trade_fut_status", "futures_symbol", "futures_exchange", "status"),
        Index("idx_fr_trade_phase_group", "phase_group", "phase_no"),
        Index("idx_fr_trade_exit_state", "status", "exit_state"),
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
