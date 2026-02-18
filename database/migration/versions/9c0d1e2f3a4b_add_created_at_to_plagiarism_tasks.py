"""Add created_at to plagiarism_tasks

Revision ID: 9c0d1e2f3a4b
Revises: 7a8b9c0d1e2f
Create Date: 2026-02-18T04:57:44.501651

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '9c0d1e2f3a4b'
down_revision = '7a8b9c0d1e2f'
branch_labels = None
depends_on = None


def upgrade():
    # Add created_at column to plagiarism_tasks table
    op.add_column('plagiarism_tasks', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()))


def downgrade():
    # Remove created_at column from plagiarism_tasks table
    op.drop_column('plagiarism_tasks', 'created_at')
