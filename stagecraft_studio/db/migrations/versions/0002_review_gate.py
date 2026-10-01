"""Add review-gate columns.

Revision ID: 0002_review
Revises: 0001_core
Create Date: 2026-10-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_review"
down_revision = "0001_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stage_run", sa.Column("evidence_json", sa.Text(), nullable=False, server_default="")
    )
    op.add_column(
        "stage_run", sa.Column("leiden_ids_json", sa.Text(), nullable=False, server_default="[]")
    )
    op.add_column(
        "stage_run",
        sa.Column("quicklook_seen", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("stage_run", sa.Column("upstream_id", sa.Integer(), nullable=True))
    op.add_column(
        "stage_run",
        sa.Column("invalidated", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("job", sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("job", "payload_json")
    op.drop_column("stage_run", "invalidated")
    op.drop_column("stage_run", "upstream_id")
    op.drop_column("stage_run", "quicklook_seen")
    op.drop_column("stage_run", "leiden_ids_json")
    op.drop_column("stage_run", "evidence_json")
