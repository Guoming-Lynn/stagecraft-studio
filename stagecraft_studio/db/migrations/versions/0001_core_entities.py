"""Create the eight core tables.

Revision ID: 0001_core
Revises:
Create Date: 2026-10-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "protocol_version",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("document_json", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "stage_run",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("project.id"), nullable=False),
        sa.Column(
            "protocol_id", sa.Integer(), sa.ForeignKey("protocol_version.id"), nullable=False
        ),
        sa.Column("protocol_hash", sa.String(64), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("engine_version", sa.String(64), nullable=False),
        sa.Column("rule_version", sa.String(64), nullable=False),
        sa.Column("stage_status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "job",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stage_run_id", sa.Integer(), sa.ForeignKey("stage_run.id"), nullable=False),
        sa.Column("task_id", sa.String(64), nullable=False),
        sa.Column("job_status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "review_decision",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stage_run_id", sa.Integer(), sa.ForeignKey("stage_run.id"), nullable=False),
        sa.Column("evidence_hash", sa.String(64), nullable=False),
        sa.Column("reviewer", sa.String(200), nullable=False),
        sa.Column("body_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "artifact",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("job.id"), nullable=False),
        sa.Column("relative_path", sa.String(500), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("artifact_status", sa.String(32), nullable=False),
    )
    op.create_table(
        "rule_result",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stage_run_id", sa.Integer(), sa.ForeignKey("stage_run.id"), nullable=False),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("rule_status", sa.String(32), nullable=False),
        sa.Column("detail_json", sa.Text(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "audit_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("detail_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    for name in (
        "audit_event",
        "rule_result",
        "artifact",
        "review_decision",
        "job",
        "stage_run",
        "protocol_version",
        "project",
    ):
        op.drop_table(name)
