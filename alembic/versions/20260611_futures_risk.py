"""Futures-Risk Options module tables.

Adds the fr_* tables for the options-trading module whose target/SL/trailing
risk is managed on the underlying futures price.

Revision ID: 20260611_futures_risk
Revises: 20260513_signal_mode
Create Date: 2026-06-11
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260611_futures_risk"
down_revision: Union[str, None] = "20260513_signal_mode"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def upgrade() -> None:
    if not _table_exists("fr_config"):
        op.create_table(
            "fr_config",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("key", sa.String(length=100), nullable=False),
            sa.Column("value", sa.Text(), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("is_editable", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_fr_config_key", "fr_config", ["key"], unique=True)

    if not _table_exists("fr_target_level"):
        op.create_table(
            "fr_target_level",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("points", sa.Float(), nullable=False),
            sa.Column("exit_pct", sa.Float(), nullable=False, server_default="0"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("idx_fr_target_seq", "fr_target_level", ["seq"], unique=True)

    if not _table_exists("fr_symbol_map"):
        op.create_table(
            "fr_symbol_map",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("underlying", sa.String(length=50), nullable=False),
            sa.Column("underlying_exchange", sa.String(length=20), nullable=False, server_default="NSE_INDEX"),
            sa.Column("futures_symbol", sa.String(length=100), nullable=True),
            sa.Column("futures_exchange", sa.String(length=20), nullable=False, server_default="NFO"),
            sa.Column("lot_size", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("auto_resolve", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_fr_symbol_map_underlying", "fr_symbol_map", ["underlying"], unique=True)

    if not _table_exists("fr_trade"):
        op.create_table(
            "fr_trade",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("mode", sa.String(length=10), nullable=False, server_default="live"),
            sa.Column("underlying", sa.String(length=50), nullable=False),
            sa.Column("option_symbol", sa.String(length=100), nullable=False),
            sa.Column("option_exchange", sa.String(length=20), nullable=False),
            sa.Column("option_type", sa.String(length=2), nullable=False),
            sa.Column("side", sa.String(length=4), nullable=False),
            sa.Column("product", sa.String(length=10), nullable=False, server_default="MIS"),
            sa.Column("expiry", sa.String(length=20), nullable=True),
            sa.Column("strike", sa.Float(), nullable=True),
            sa.Column("lots", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("lot_size", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("total_qty", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("remaining_qty", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("entry_option_price", sa.Float(), nullable=False, server_default="0"),
            sa.Column("entry_order_id", sa.String(length=60), nullable=True),
            sa.Column("futures_symbol", sa.String(length=100), nullable=False),
            sa.Column("futures_exchange", sa.String(length=20), nullable=False, server_default="NFO"),
            sa.Column("entry_futures_price", sa.Float(), nullable=False, server_default="0"),
            sa.Column("direction", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("sl_points", sa.Float(), nullable=False, server_default="0"),
            sa.Column("sl_price", sa.Float(), nullable=False, server_default="0"),
            sa.Column("sl_basis", sa.String(length=20), nullable=False, server_default="initial"),
            sa.Column("status", sa.String(length=12), nullable=False, server_default="active"),
            sa.Column("realized_pnl", sa.Float(), nullable=False, server_default="0"),
            sa.Column("meta", JSONB(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_fr_trade_user_id", "fr_trade", ["user_id"])
        op.create_index("ix_fr_trade_status", "fr_trade", ["status"])
        op.create_index("idx_fr_trade_user_status", "fr_trade", ["user_id", "status"])
        op.create_index("idx_fr_trade_fut_status", "fr_trade", ["futures_symbol", "futures_exchange", "status"])

    if not _table_exists("fr_trade_target"):
        op.create_table(
            "fr_trade_target",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("trade_id", sa.Integer(), sa.ForeignKey("fr_trade.id", ondelete="CASCADE"), nullable=False),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("points", sa.Float(), nullable=False),
            sa.Column("exit_pct", sa.Float(), nullable=False, server_default="0"),
            sa.Column("trigger_price", sa.Float(), nullable=False),
            sa.Column("exit_qty", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=10), nullable=False, server_default="pending"),
            sa.Column("hit_futures_price", sa.Float(), nullable=True),
            sa.Column("exit_order_id", sa.String(length=60), nullable=True),
            sa.Column("hit_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_fr_trade_target_trade_id", "fr_trade_target", ["trade_id"])
        op.create_index("idx_fr_tgt_trade_seq", "fr_trade_target", ["trade_id", "seq"], unique=True)

    if not _table_exists("fr_trade_event"):
        op.create_table(
            "fr_trade_event",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("trade_id", sa.Integer(), sa.ForeignKey("fr_trade.id", ondelete="CASCADE"), nullable=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("kind", sa.String(length=20), nullable=False),
            sa.Column("severity", sa.String(length=10), nullable=False, server_default="info"),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("payload", JSONB(), nullable=True),
        )
        op.create_index("ix_fr_trade_event_trade_id", "fr_trade_event", ["trade_id"])
        op.create_index("ix_fr_trade_event_user_id", "fr_trade_event", ["user_id"])
        op.create_index("idx_fr_event_trade_ts", "fr_trade_event", ["trade_id", "ts"])
        op.create_index("idx_fr_event_user_ts", "fr_trade_event", ["user_id", "ts"])


def downgrade() -> None:
    for tbl in (
        "fr_trade_event",
        "fr_trade_target",
        "fr_trade",
        "fr_symbol_map",
        "fr_target_level",
        "fr_config",
    ):
        if _table_exists(tbl):
            op.drop_table(tbl)
