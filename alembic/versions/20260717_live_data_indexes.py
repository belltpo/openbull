"""Add live symbol-search and option-chain indexes.

Revision ID: 20260717_live_data_indexes
Revises: 20260701_fr_target_templates
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260717_live_data_indexes"
down_revision: Union[str, None] = "20260701_fr_target_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pg_trgm lets the existing user-facing contains search use an index rather
    # than scanning 200k+ master-contract rows for every keystroke.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_symtoken_exchange_type_symbol "
        "ON symtoken (exchange, instrumenttype, symbol)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_symtoken_symbol_trgm "
        "ON symtoken USING gin (symbol gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_symtoken_brsymbol_trgm "
        "ON symtoken USING gin (brsymbol gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_symtoken_name_trgm "
        "ON symtoken USING gin (name gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_symtoken_name_trgm")
    op.execute("DROP INDEX IF EXISTS idx_symtoken_brsymbol_trgm")
    op.execute("DROP INDEX IF EXISTS idx_symtoken_symbol_trgm")
    op.execute("DROP INDEX IF EXISTS idx_symtoken_exchange_type_symbol")
