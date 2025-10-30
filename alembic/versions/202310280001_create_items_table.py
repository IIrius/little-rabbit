"""Create items table

Revision ID: 202310280001
Revises: 
Create Date: 2023-10-28 00:01:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "202310280001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("items")
