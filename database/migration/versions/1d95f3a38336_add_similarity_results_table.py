"""Add similarity_results table

Revision ID: 1d95f3a38336
Revises: 9c84f2e27225
Create Date: 2026-02-07 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '1d95f3a38336'
down_revision = '9c84f2e27225'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "similarity_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("plagiarism_tasks.id"), nullable=False),
        sa.Column("file_a_id", sa.String(36), sa.ForeignKey("files.id"), nullable=False),
        sa.Column("file_b_id", sa.String(36), sa.ForeignKey("files.id"), nullable=False),
        sa.Column("token_similarity", sa.Float(), nullable=True),
        sa.Column("ast_similarity", sa.Float(), nullable=True),
        sa.Column("matches", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table("similarity_results")
