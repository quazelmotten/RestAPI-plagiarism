"""Merge task cleanup indexes and file embeddings branches

Revision ID: merge_cleanup_embeddings
Revises: add_task_cleanup_indexes, a1b2c3d4e5f8
Create Date: 2026-05-20 12:00:00.000000

"""

from alembic import op

revision = "merge_cleanup_embeddings"
down_revision = ("add_task_cleanup_indexes", "a1b2c3d4e5f8")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
