"""add reviewed_by and detection_source to similarity_results

Revision ID: a5152c7df72e
Revises: add_user_username_column
Create Date: 2026-05-05 01:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a5152c7df72e'
down_revision = 'add_user_username_column'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add reviewed_by and detection_source columns to similarity_results table."""
    # Add reviewed_by column (UUID, nullable)
    op.add_column('similarity_results', sa.Column('reviewed_by', sa.UUID(), nullable=True))
    
    # Add detection_source column (String(10), nullable)
    op.add_column('similarity_results', sa.Column('detection_source', sa.String(10), nullable=True))


def downgrade() -> None:
    """Remove reviewed_by and detection_source columns from similarity_results table."""
    op.drop_column('similarity_results', 'detection_source')
    op.drop_column('similarity_results', 'reviewed_by')
