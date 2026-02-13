"""Add progress tracking columns to plagiarism_tasks

Revision ID: 5f4a2c8d1e9f
Revises: 2a8c9e1f45b2
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '5f4a2c8d1e9f'
down_revision = '2a8c9e1f45b2'
branch_labels = None
depends_on = None


def upgrade():
    # Add total_pairs column
    op.add_column(
        'plagiarism_tasks',
        sa.Column('total_pairs', sa.Integer(), nullable=True)
    )
    
    # Add processed_pairs column
    op.add_column(
        'plagiarism_tasks',
        sa.Column('processed_pairs', sa.Integer(), nullable=True)
    )
    
    # Add progress percentage column (calculated field, but stored for efficiency)
    op.add_column(
        'plagiarism_tasks',
        sa.Column('progress', sa.Float(), nullable=True)
    )


def downgrade():
    op.drop_column('plagiarism_tasks', 'progress')
    op.drop_column('plagiarism_tasks', 'processed_pairs')
    op.drop_column('plagiarism_tasks', 'total_pairs')
