"""Add root_path column to project table.

Revision ID: 0003_project_root
Revises: 0002_review
Create Date: 2026-10-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_project_root"
down_revision = "0002_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project",
        sa.Column("root_path", sa.String(500), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("project", "root_path")
