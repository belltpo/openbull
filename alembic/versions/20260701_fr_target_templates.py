"""Add Futures-Risk target templates.

Revision ID: 20260701_fr_target_templates
Revises: 20260611_futures_risk
Create Date: 2026-07-01
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260701_fr_target_templates"
down_revision: Union[str, None] = "20260611_futures_risk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _indexes(table: str) -> set[str]:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {ix["name"] for ix in insp.get_indexes(table)}


def _has_template_fk() -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "fr_target_level" not in insp.get_table_names():
        return False
    for fk in insp.get_foreign_keys("fr_target_level"):
        if fk.get("referred_table") == "fr_target_template" and fk.get("constrained_columns") == ["template_id"]:
            return True
    return False


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists("fr_target_template"):
        op.create_table(
            "fr_target_template",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    if "ix_fr_target_template_name" not in _indexes("fr_target_template"):
        op.create_index("ix_fr_target_template_name", "fr_target_template", ["name"], unique=True)
    if "idx_fr_target_template_default" not in _indexes("fr_target_template"):
        op.create_index("idx_fr_target_template_default", "fr_target_template", ["is_default"])

    default_id = bind.execute(sa.text("SELECT id FROM fr_target_template WHERE is_default = TRUE LIMIT 1")).scalar()
    if default_id is None:
        default_id = bind.execute(
            sa.text(
                "INSERT INTO fr_target_template (name, description, is_default, enabled) "
                "VALUES (:name, :description, TRUE, TRUE) RETURNING id"
            ),
            {
                "name": "Default",
                "description": "Default target plan migrated from the original target levels.",
            },
        ).scalar_one()

    cols = _columns("fr_target_level")
    if "fr_target_level" in sa.inspect(bind).get_table_names() and "template_id" not in cols:
        op.add_column("fr_target_level", sa.Column("template_id", sa.Integer(), nullable=True))

    if _table_exists("fr_target_level"):
        bind.execute(
            sa.text("UPDATE fr_target_level SET template_id = :tid WHERE template_id IS NULL"),
            {"tid": default_id},
        )
        bind.execute(sa.text('ALTER TABLE "fr_target_level" ALTER COLUMN "template_id" SET NOT NULL'))
        if "ix_fr_target_level_template_id" not in _indexes("fr_target_level"):
            op.create_index("ix_fr_target_level_template_id", "fr_target_level", ["template_id"])
        if "idx_fr_target_seq" in _indexes("fr_target_level"):
            op.drop_index("idx_fr_target_seq", table_name="fr_target_level")
        if "idx_fr_target_template_seq" not in _indexes("fr_target_level"):
            op.create_index(
                "idx_fr_target_template_seq",
                "fr_target_level",
                ["template_id", "seq"],
                unique=True,
            )
        if not _has_template_fk():
            op.create_foreign_key(
                "fk_fr_target_level_template_id",
                "fr_target_level",
                "fr_target_template",
                ["template_id"],
                ["id"],
                ondelete="CASCADE",
            )


def downgrade() -> None:
    if _table_exists("fr_target_level"):
        if "idx_fr_target_template_seq" in _indexes("fr_target_level"):
            op.drop_index("idx_fr_target_template_seq", table_name="fr_target_level")
        if "ix_fr_target_level_template_id" in _indexes("fr_target_level"):
            op.drop_index("ix_fr_target_level_template_id", table_name="fr_target_level")
        if "template_id" in _columns("fr_target_level"):
            op.drop_column("fr_target_level", "template_id")
        if "idx_fr_target_seq" not in _indexes("fr_target_level"):
            op.create_index("idx_fr_target_seq", "fr_target_level", ["seq"], unique=True)
    if _table_exists("fr_target_template"):
        op.drop_table("fr_target_template")
