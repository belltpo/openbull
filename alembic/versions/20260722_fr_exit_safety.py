"""Add persistent Futures-Risk exit safety and reconciliation state.

Revision ID: 20260722_fr_exit_safety
Revises: 20260717_live_data_indexes
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260722_fr_exit_safety"
down_revision: Union[str, None] = "20260717_live_data_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    columns = _column_names("fr_trade")
    additions = (
        ("exit_state", sa.Column("exit_state", sa.String(length=20), nullable=False, server_default="idle")),
        ("exit_attempt_id", sa.Column("exit_attempt_id", sa.String(length=36), nullable=True)),
        ("exit_attempt_reason", sa.Column("exit_attempt_reason", sa.String(length=20), nullable=True)),
        ("exit_attempted_at", sa.Column("exit_attempted_at", sa.DateTime(timezone=True), nullable=True)),
        ("exit_failure_count", sa.Column("exit_failure_count", sa.Integer(), nullable=False, server_default="0")),
        ("exit_block_reason", sa.Column("exit_block_reason", sa.Text(), nullable=True)),
        ("last_exit_order_id", sa.Column("last_exit_order_id", sa.String(length=60), nullable=True)),
        ("broker_remaining_qty", sa.Column("broker_remaining_qty", sa.Integer(), nullable=True)),
        ("broker_reconciled_at", sa.Column("broker_reconciled_at", sa.DateTime(timezone=True), nullable=True)),
    )
    for name, column in additions:
        if name not in columns:
            op.add_column("fr_trade", column)

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_fr_trade_exit_state "
        "ON fr_trade (status, exit_state)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_fr_trade_exit_state")
    columns = _column_names("fr_trade")
    for name in (
        "broker_reconciled_at",
        "broker_remaining_qty",
        "last_exit_order_id",
        "exit_block_reason",
        "exit_failure_count",
        "exit_attempted_at",
        "exit_attempt_reason",
        "exit_attempt_id",
        "exit_state",
    ):
        if name in columns:
            op.drop_column("fr_trade", name)
