"""Add unique constraint to similarity_results

Revision ID: 6e7d8f9a1023
Revises: 5f4a2c8d1e9f
Create Date: 2026-02-13 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '6e7d8f9a1023'
down_revision = '5f4a2c8d1e9f'
branch_labels = None
depends_on = None


def upgrade():
    # Create unique index to prevent duplicate results for the same file pair in a task
    op.create_index(
        'idx_similarity_unique_pair',
        'similarity_results',
        ['task_id', 'file_a_id', 'file_b_id'],
        unique=True
    )


def downgrade():
    op.drop_index('idx_similarity_unique_pair', table_name='similarity_results')
