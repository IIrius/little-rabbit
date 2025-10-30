"""Add processing records table for pipeline logging."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "202310280004"
down_revision = "202310280003"
branch_labels = None
depends_on = None

PROCESSING_OUTCOME_ENUM = sa.Enum(
    "publish",
    "moderate",
    "reject",
    name="processing_outcome",
)


def upgrade() -> None:
    bind = op.get_bind()
    PROCESSING_OUTCOME_ENUM.create(bind, checkfirst=True)

    op.create_table(
        "processing_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace", sa.String(length=64), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=False),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("outcome", PROCESSING_OUTCOME_ENUM, nullable=False),
        sa.Column("status_reason", sa.String(length=255), nullable=True),
        sa.Column("dedup_reason", sa.String(length=255), nullable=True),
        sa.Column("translation_language", sa.String(length=8), nullable=True),
        sa.Column(
            "fake_detected",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "fake_confidence",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "classification_score",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("classification_summary", sa.Text(), nullable=True),
        sa.Column("classification_flags", sa.Text(), nullable=True),
        sa.Column("logs", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "workspace", "reference", name="uq_processing_workspace_reference"
        ),
    )
    op.create_index(
        "ix_processing_records_workspace",
        "processing_records",
        ["workspace"],
    )
    op.create_index(
        "ix_processing_records_fingerprint",
        "processing_records",
        ["fingerprint"],
    )


def downgrade() -> None:
    op.drop_index("ix_processing_records_fingerprint", table_name="processing_records")
    op.drop_index("ix_processing_records_workspace", table_name="processing_records")
    op.drop_table("processing_records")
    PROCESSING_OUTCOME_ENUM.drop(op.get_bind(), checkfirst=True)
