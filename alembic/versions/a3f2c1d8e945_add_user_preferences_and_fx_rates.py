"""add user_preferences and fx_rates tables

Revision ID: a3f2c1d8e945
Revises: 051811ee099b
Create Date: 2026-06-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3f2c1d8e945"
down_revision: Union[str, None] = "051811ee099b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = sa.inspect(bind).get_table_names()

    if "user_preferences" not in existing:
        op.create_table(
            "user_preferences",
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("main_currency", sa.String(length=10), nullable=False, server_default="BRL"),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("user_id"),
        )

    if "fx_rates" not in existing:
        op.create_table(
            "fx_rates",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("rate_date", sa.Date(), nullable=False),
            sa.Column("from_currency", sa.String(length=10), nullable=False),
            sa.Column("to_currency", sa.String(length=10), nullable=False),
            sa.Column("rate", sa.Numeric(precision=18, scale=6), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "rate_date", "from_currency", "to_currency", name="uq_fx_rate_date_pair"
            ),
        )
        op.create_index("ix_fx_rates_lookup", "fx_rates", ["from_currency", "to_currency", "rate_date"])


def downgrade() -> None:
    bind = op.get_bind()
    existing = sa.inspect(bind).get_table_names()
    if "fx_rates" in existing:
        op.drop_index("ix_fx_rates_lookup", table_name="fx_rates")
        op.drop_table("fx_rates")
    if "user_preferences" in existing:
        op.drop_table("user_preferences")
