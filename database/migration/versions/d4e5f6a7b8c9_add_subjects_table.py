"""Add subjects table and subject_id to assignments

Revision ID: d4e5f6a7b8c9
Revises: a1b2c3d4e5f6
Create Date: 2026-04-05 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "3b7d5e9f2a1c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "subjects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.add_column(
        "assignments",
        sa.Column("subject_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "assignments_subject_id_fkey",
        "assignments",
        "subjects",
        ["subject_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint("assignments_subject_id_fkey", "assignments", type_="foreignkey")
    op.drop_column("assignments", "subject_id")
    op.drop_table("subjects")
