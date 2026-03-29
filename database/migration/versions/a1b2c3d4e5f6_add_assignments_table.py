"""Add assignments table and assignment_id to plagiarism_tasks

Revision ID: a1b2c3d4e5f6
Revises: 9c0d1e2f3a4b
Create Date: 2026-03-29 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "9c0d1e2f3a4b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assignments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.add_column(
        "plagiarism_tasks",
        sa.Column("assignment_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "plagiarism_tasks_assignment_id_fkey",
        "plagiarism_tasks",
        "assignments",
        ["assignment_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint(
        "plagiarism_tasks_assignment_id_fkey", "plagiarism_tasks", type_="foreignkey"
    )
    op.drop_column("plagiarism_tasks", "assignment_id")
    op.drop_table("assignments")
