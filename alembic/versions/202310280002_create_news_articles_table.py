"""Create news_articles table

Revision ID: 202310280002
Revises: 202310280001
Create Date: 2023-10-28 00:02:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "202310280002"
down_revision = "202310280001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "news_articles",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("workspace", sa.String(length=64), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author", sa.String(length=120), nullable=True),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("workspace", "slug", name="uq_news_workspace_slug"),
    )
    op.create_index(
        "ix_news_articles_workspace",
        "news_articles",
        ["workspace"],
    )


def downgrade() -> None:
    op.drop_index("ix_news_articles_workspace", table_name="news_articles")
    op.drop_table("news_articles")
