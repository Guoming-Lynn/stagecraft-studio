"""Add isolated M6 provider, call, and proposal records."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_assistant"
down_revision = "0003_project_root"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_profile",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("capabilities_json", sa.Text(), nullable=False),
        sa.Column("credential_id", sa.String(64), nullable=False),
    )
    op.create_table(
        "llm_call",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("stage_run_id", sa.Integer(), sa.ForeignKey("stage_run.id"), nullable=True),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("sources_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "proposal",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("call_id", sa.String(32), sa.ForeignKey("llm_call.id"), nullable=False),
        sa.Column("stage_run_id", sa.Integer(), sa.ForeignKey("stage_run.id"), nullable=True),
        sa.Column("body_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("proposal")
    op.drop_table("llm_call")
    op.drop_table("provider_profile")
