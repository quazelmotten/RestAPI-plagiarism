"""add reviewed_by and detection_source to similarity_results

Revision ID: a5152c7df72e
Revises: add_user_username_column
Create Date: 2026-05-05 01:30:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'a5152c7df72e'
down_revision = 'add_user_username_column'  # Create linear chain
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add reviewed_by and detection_source columns to similarity_results table."""
    # Make idempotent - check if columns exist before adding
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('similarity_results')]

    # Add reviewed_by column (UUID, nullable) if not exists
    if 'reviewed_by' not in existing_columns:
        op.add_column('similarity_results', sa.Column('reviewed_by', sa.UUID(), nullable=True))

    # Add detection_source column (String(10), nullable) if not exists
    if 'detection_source' not in existing_columns:
        op.add_column('similarity_results', sa.Column('detection_source', sa.String(10), nullable=True))


def downgrade() -> None:
    """Remove reviewed_by and detection_source columns from similarity_results table."""
    op.drop_column('similarity_results', 'detection_source')
    op.drop_column('similarity_results', 'reviewed_by')
