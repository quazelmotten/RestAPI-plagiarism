"""Add name and language columns to plagiarism_tasks

Revision ID: add_task_name_and_language
Revises: merge_cleanup_embeddings
Create Date: 2026-05-21 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "add_task_name_and_language"
down_revision = "merge_cleanup_embeddings"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Add name column (nullable, for backward compatibility)
    result = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'plagiarism_tasks' AND column_name = 'name'"
        )
    )
    if not result.fetchone():
        op.add_column("plagiarism_tasks", sa.Column("name", sa.String(255), nullable=True))

    # Add language column (nullable, defaults to 'python' at application level)
    result = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'plagiarism_tasks' AND column_name = 'language'"
        )
    )
    if not result.fetchone():
        op.add_column("plagiarism_tasks", sa.Column("language", sa.String(50), nullable=True))

    # Add indexes for filtering
    result = conn.execute(
        sa.text(
            "SELECT indexname FROM pg_indexes WHERE indexname = 'ix_plagiarism_tasks_name'"
        )
    )
    if not result.fetchone():
        op.create_index("ix_plagiarism_tasks_name", "plagiarism_tasks", ["name"])

    result = conn.execute(
        sa.text(
            "SELECT indexname FROM pg_indexes WHERE indexname = 'ix_plagiarism_tasks_language'"
        )
    )
    if not result.fetchone():
        op.create_index("ix_plagiarism_tasks_language", "plagiarism_tasks", ["language"])

    result = conn.execute(
        sa.text(
            "SELECT indexname FROM pg_indexes WHERE indexname = 'ix_plagiarism_tasks_assignment_id_status'"
        )
    )
    if not result.fetchone():
        op.create_index(
            "ix_plagiarism_tasks_assignment_id_status",
            "plagiarism_tasks",
            ["assignment_id", "status"],
        )


def downgrade():
    op.drop_index("ix_plagiarism_tasks_assignment_id_status", table_name="plagiarism_tasks")
    op.drop_index("ix_plagiarism_tasks_language", table_name="plagiarism_tasks")
    op.drop_index("ix_plagiarism_tasks_name", table_name="plagiarism_tasks")
    op.drop_column("plagiarism_tasks", "language")
    op.drop_column("plagiarism_tasks", "name")
