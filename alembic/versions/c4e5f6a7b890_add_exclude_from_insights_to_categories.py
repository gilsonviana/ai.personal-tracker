"""add exclude_from_insights to categories

Revision ID: c4e5f6a7b890
Revises: a3f2c1d8e945
Create Date: 2026-06-06 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4e5f6a7b890"
down_revision: Union[str, None] = "a3f2c1d8e945"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("exclude_from_insights", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("categories", "exclude_from_insights")
