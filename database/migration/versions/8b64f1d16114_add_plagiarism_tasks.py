"""Add plagiarism tasks table

Revision ID: 8b64f1d16114
Revises: 
Create Date: 2026-02-05 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '8b64f1d16114'
down_revision = '8b64f1d16118'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "plagiarism_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("similarity", sa.Float()),
        sa.Column("matches", postgresql.JSONB()),
        sa.Column("error", sa.Text()),
    )

def downgrade():
    op.drop_table("plagiarism_tasks")
