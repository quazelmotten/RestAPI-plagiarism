"""Remove token_similarity column from similarity_results

Revision ID: 7a8b9c0d1e2f
Revises: 6e7d8f9a1023
Create Date: 2026-02-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '7a8b9c0d1e2f'
down_revision = '6e7d8f9a1023'
branch_labels = None
depends_on = None

def upgrade():
    # Drop token_similarity column from similarity_results table
    op.drop_column('similarity_results', 'token_similarity')

def downgrade():
    # Add token_similarity column back to similarity_results table
    op.add_column(
        'similarity_results',
        sa.Column('token_similarity', sa.Float(), nullable=True)
    )
