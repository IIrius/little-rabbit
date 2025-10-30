"""Create workspace dashboard tables

Revision ID: 202310280003
Revises: 202310280002
Create Date: 2023-10-28 00:03:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "202310280003"
down_revision = "202310280002"
branch_labels = None
depends_on = None


SOURCE_KIND_ENUM = sa.Enum(
    "rss",
    "api",
    "telegram",
    "custom",
    name="workspace_source_kind",
)
PROXY_PROTOCOL_ENUM = sa.Enum(
    "http",
    "https",
    "socks5",
    name="workspace_proxy_protocol",
)
PIPELINE_STATUS_ENUM = sa.Enum(
    "queued",
    "running",
    "success",
    "failure",
    name="pipeline_run_status",
)


def upgrade() -> None:
    bind = op.get_bind()
    SOURCE_KIND_ENUM.create(bind, checkfirst=True)
    PROXY_PROTOCOL_ENUM.create(bind, checkfirst=True)
    PIPELINE_STATUS_ENUM.create(bind, checkfirst=True)

    op.create_table(
        "workspace_sources",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("workspace", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", SOURCE_KIND_ENUM, nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("workspace", "name", name="uq_workspace_source_name"),
    )
    op.create_index(
        "ix_workspace_sources_workspace",
        "workspace_sources",
        ["workspace"],
    )

    op.create_table(
        "workspace_proxies",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("workspace", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("protocol", PROXY_PROTOCOL_ENUM, nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("workspace", "name", name="uq_workspace_proxy_name"),
        sa.UniqueConstraint("workspace", "address", name="uq_workspace_proxy_address"),
    )
    op.create_index(
        "ix_workspace_proxies_workspace",
        "workspace_proxies",
        ["workspace"],
    )

    op.create_table(
        "workspace_telegram_channels",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("workspace", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("chat_id", sa.String(length=64), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("workspace", "name", name="uq_workspace_telegram_name"),
        sa.UniqueConstraint("workspace", "chat_id", name="uq_workspace_telegram_chat"),
    )
    op.create_index(
        "ix_workspace_telegram_channels_workspace",
        "workspace_telegram_channels",
        ["workspace"],
    )

    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("workspace", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("status", PIPELINE_STATUS_ENUM, nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("workspace", "task_id", name="uq_pipeline_run_task"),
    )
    op.create_index(
        "ix_pipeline_runs_workspace",
        "pipeline_runs",
        ["workspace"],
    )


def downgrade() -> None:
    op.drop_index("ix_pipeline_runs_workspace", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")

    op.drop_index(
        "ix_workspace_telegram_channels_workspace",
        table_name="workspace_telegram_channels",
    )
    op.drop_table("workspace_telegram_channels")

    op.drop_index("ix_workspace_proxies_workspace", table_name="workspace_proxies")
    op.drop_table("workspace_proxies")

    op.drop_index("ix_workspace_sources_workspace", table_name="workspace_sources")
    op.drop_table("workspace_sources")

    bind = op.get_bind()
    PIPELINE_STATUS_ENUM.drop(bind, checkfirst=True)
    PROXY_PROTOCOL_ENUM.drop(bind, checkfirst=True)
    SOURCE_KIND_ENUM.drop(bind, checkfirst=True)
