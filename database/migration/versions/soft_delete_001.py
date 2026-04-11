"""add deleted_at columns for soft delete

Revision ID: soft_delete_001
Revises: d4e5f6a7b8c9
Create Date: 2026-04-07 10:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'soft_delete_001'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add deleted_at column to subjects table
    op.add_column('subjects', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))

    # Add deleted_at column to assignments table
    op.add_column('assignments', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))

    # Add deleted_at column to plagiarism_tasks table (for consistency)
    op.add_column('plagiarism_tasks', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))

    # Add deleted_at column to files table (for consistency)
    op.add_column('files', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))

    # Add deleted_at column to similarity_results table (for consistency)
    op.add_column('similarity_results', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Remove deleted_at columns
    op.drop_column('similarity_results', 'deleted_at')
    op.drop_column('files', 'deleted_at')
    op.drop_column('plagiarism_tasks', 'deleted_at')
    op.drop_column('assignments', 'deleted_at')
    op.drop_column('subjects', 'deleted_at')
