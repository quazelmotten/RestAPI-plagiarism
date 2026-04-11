"""Add review_disposition to similarity_results

Revision ID: add_review_disposition_001
Revises: fix_unique_constraints_001
Create Date: 2026-04-10 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "add_review_disposition_001"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "similarity_results", sa.Column("review_disposition", sa.String(20), nullable=True)
    )
    op.add_column(
        "similarity_results", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("similarity_results", "reviewed_at")
    op.drop_column("similarity_results", "review_disposition")
