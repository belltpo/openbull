"""
Idempotent startup micro-migrations.

OpenBull primarily manages schema via ``Base.metadata.create_all(...)`` on
startup. That handles *new* tables but **does not alter** existing ones, so
when a column is added to a model the live DB drifts away from the code.

This module closes that gap with minimal machinery:

* Each migration is a pure ``(inspector, engine) -> None`` function.
* All migrations are idempotent — they check whether they've already been
  applied and no-op if so.
* They run after ``create_all`` on every startup, so adding a new column to
  an existing table only needs two things: update the model, and append one
  ``_add_column_if_missing`` call here.

For anything more complex than a nullable column add, use Alembic.
"""

from __future__ import annotations

import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from backend.config import get_settings

logger = logging.getLogger(__name__)


def _add_column_if_missing(
    engine: Engine, table: str, column: str, column_ddl: str
) -> None:
    """Execute ``ALTER TABLE <table> ADD COLUMN <column> <column_ddl>`` if the
    table exists and the column is missing. Safe to call on every startup."""
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return  # create_all will create it fresh with every column from the model
    existing_cols = {c["name"] for c in insp.get_columns(table)}
    if column in existing_cols:
        return
    with engine.begin() as conn:
        conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {column_ddl}'))
    logger.info("Schema migration: added column %s.%s", table, column)


def _add_index_if_missing(
    engine: Engine, table: str, index_name: str, columns: list[str]
) -> None:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return
    existing = {ix["name"] for ix in insp.get_indexes(table)}
    if index_name in existing:
        return
    col_list = ", ".join(f'"{c}"' for c in columns)
    with engine.begin() as conn:
        conn.execute(
            text(f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{table}" ({col_list})')
        )
    logger.info("Schema migration: created index %s on %s(%s)", index_name, table, col_list)


def _migrate_fr_target_templates(engine: Engine) -> None:
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    if "fr_target_level" not in tables:
        return

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS fr_target_template (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    description VARCHAR(500),
                    is_default BOOLEAN NOT NULL DEFAULT FALSE,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(
            text(
                'CREATE INDEX IF NOT EXISTS "idx_fr_target_template_default" '
                'ON "fr_target_template" ("is_default")'
            )
        )
        default_id = conn.execute(
            text("SELECT id FROM fr_target_template WHERE is_default = TRUE LIMIT 1")
        ).scalar()
        if default_id is None:
            default_id = conn.execute(
                text(
                    "INSERT INTO fr_target_template (name, description, is_default, enabled) "
                    "VALUES (:name, :description, TRUE, TRUE) RETURNING id"
                ),
                {
                    "name": "Default",
                    "description": "Default target plan migrated from the original target levels.",
                },
            ).scalar_one()

        cols = {c["name"] for c in inspect(conn).get_columns("fr_target_level")}
        if "template_id" not in cols:
            conn.execute(text('ALTER TABLE "fr_target_level" ADD COLUMN "template_id" INTEGER'))
        conn.execute(
            text("UPDATE fr_target_level SET template_id = :tid WHERE template_id IS NULL"),
            {"tid": default_id},
        )
        conn.execute(text('ALTER TABLE "fr_target_level" ALTER COLUMN "template_id" SET NOT NULL'))
        conn.execute(text('DROP INDEX IF EXISTS "idx_fr_target_seq"'))
        conn.execute(
            text(
                'CREATE INDEX IF NOT EXISTS "ix_fr_target_level_template_id" '
                'ON "fr_target_level" ("template_id")'
            )
        )
        conn.execute(
            text(
                'CREATE UNIQUE INDEX IF NOT EXISTS "idx_fr_target_template_seq" '
                'ON "fr_target_level" ("template_id", "seq")'
            )
        )


def run_startup_migrations() -> None:
    """Apply every pending in-place migration. Called from the app lifespan."""
    engine = create_engine(get_settings().sync_database_url, future=True)
    try:
        # Phase 3: api_logs gained a `mode` column + companion index.
        _add_column_if_missing(engine, "api_logs", "mode", "VARCHAR(10)")
        _add_index_if_missing(
            engine, "api_logs", "idx_api_logs_mode_created", ["mode", "created_at"]
        )

        # Phase 2c: sandbox margin model now matches openalgo's transfer-on-fill
        # design. Margin is locked against the position once an order fills, and
        # pro-rata released on reduce/close. New columns:
        _add_column_if_missing(
            engine, "sandbox_positions", "margin_blocked", "DOUBLE PRECISION NOT NULL DEFAULT 0"
        )
        _add_column_if_missing(
            engine, "sandbox_positions", "today_realized_pnl", "DOUBLE PRECISION NOT NULL DEFAULT 0"
        )
        _add_column_if_missing(
            engine, "sandbox_funds", "today_realized_pnl", "DOUBLE PRECISION NOT NULL DEFAULT 0"
        )
        # Phase 2c continued: holdings get a settlement_date so the UI can
        # show the T+1 settle day. Nullable — historical rows won't have it.
        _add_column_if_missing(
            engine, "sandbox_holdings", "settlement_date", "VARCHAR(10)"
        )

        # Signal-mode strategy module (docs/plan/strategy-signal-mode.md):
        # adds two columns to sm_strategy so the same table can back both
        # batch-mode (existing) and signal-mode (new) strategies. Defaults
        # preserve every existing row's semantics with no backfill.
        _add_column_if_missing(
            engine, "sm_strategy", "strategy_kind",
            "VARCHAR(20) NOT NULL DEFAULT 'batch'",
        )
        _add_column_if_missing(
            engine, "sm_strategy", "direction",
            "VARCHAR(20) NOT NULL DEFAULT 'both'",
        )

        # Kill-switch column. When True, webhook handler refuses every
        # signal for the strategy. Set by /kill_switch (which also
        # flattens positions); cleared by /unlock_webhook.
        _add_column_if_missing(
            engine, "sm_strategy", "webhook_locked",
            "BOOLEAN NOT NULL DEFAULT FALSE",
        )

        # Futures-Risk Phase A: audit actors on fr_trade (who created / last
        # modified). Nullable — historical rows keep NULL.
        _add_column_if_missing(engine, "fr_trade", "created_by", "INTEGER")
        _add_column_if_missing(engine, "fr_trade", "modified_by", "INTEGER")

        # Futures-Risk Phase B: phase tracking + close timestamp.
        _add_column_if_missing(engine, "fr_trade", "phase_group", "VARCHAR(120)")
        _add_column_if_missing(engine, "fr_trade", "phase_no", "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(engine, "fr_trade", "closed_at", "TIMESTAMPTZ")
        _add_index_if_missing(
            engine, "fr_trade", "idx_fr_trade_phase_group", ["phase_group", "phase_no"]
        )

        # Futures-Risk live exit safety. These are also in the formal Alembic
        # revision, but startup micro-migrations protect installations whose
        # tables were created before Alembic was stamped (for example, a fresh
        # install resumed after an interrupted deployment).
        _add_column_if_missing(
            engine, "fr_trade", "exit_state", "VARCHAR(20) NOT NULL DEFAULT 'idle'"
        )
        _add_column_if_missing(engine, "fr_trade", "exit_attempt_id", "VARCHAR(36)")
        _add_column_if_missing(engine, "fr_trade", "exit_attempt_reason", "VARCHAR(20)")
        _add_column_if_missing(engine, "fr_trade", "exit_attempted_at", "TIMESTAMPTZ")
        _add_column_if_missing(
            engine, "fr_trade", "exit_failure_count", "INTEGER NOT NULL DEFAULT 0"
        )
        _add_column_if_missing(engine, "fr_trade", "exit_block_reason", "TEXT")
        _add_column_if_missing(engine, "fr_trade", "last_exit_order_id", "VARCHAR(60)")
        _add_column_if_missing(engine, "fr_trade", "broker_remaining_qty", "INTEGER")
        _add_column_if_missing(engine, "fr_trade", "broker_reconciled_at", "TIMESTAMPTZ")
        _add_index_if_missing(
            engine, "fr_trade", "idx_fr_trade_exit_state", ["status", "exit_state"]
        )

        # Futures-Risk target templates: preserve the old global target list as
        # the Default template, then scope target seq uniqueness per template.
        _migrate_fr_target_templates(engine)
    except Exception:
        logger.exception("Startup schema migration failed")
    finally:
        engine.dispose()
