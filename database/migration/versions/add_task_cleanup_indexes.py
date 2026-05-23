"""Add indexes for task cleanup and orphan management

Revision ID: add_task_cleanup_indexes
Revises: add_bulk_operation_indexes
Create Date: 2026-05-20 10:00:00.000000

"""

from alembic import op
from sqlalchemy import text

revision = "add_task_cleanup_indexes"
down_revision = "add_bulk_operation_indexes"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    result = conn.execute(
        text("SELECT indexname FROM pg_indexes WHERE indexname = 'ix_plagiarism_tasks_assignment_id'")
    )
    if not result.fetchone():
        op.create_index(
            "ix_plagiarism_tasks_assignment_id",
            "plagiarism_tasks",
            ["assignment_id"],
        )

    result = conn.execute(
        text("SELECT indexname FROM pg_indexes WHERE indexname = 'ix_plagiarism_tasks_deleted_at'")
    )
    if not result.fetchone():
        op.create_index(
            "ix_plagiarism_tasks_deleted_at",
            "plagiarism_tasks",
            ["deleted_at"],
        )

    result = conn.execute(
        text("SELECT indexname FROM pg_indexes WHERE indexname = 'ix_files_task_id'")
    )
    if not result.fetchone():
        op.create_index(
            "ix_files_task_id",
            "files",
            ["task_id"],
        )

    result = conn.execute(
        text("SELECT indexname FROM pg_indexes WHERE indexname = 'ix_similarity_results_file_a_id'")
    )
    if not result.fetchone():
        op.create_index(
            "ix_similarity_results_file_a_id",
            "similarity_results",
            ["file_a_id"],
        )

    result = conn.execute(
        text("SELECT indexname FROM pg_indexes WHERE indexname = 'ix_similarity_results_file_b_id'")
    )
    if not result.fetchone():
        op.create_index(
            "ix_similarity_results_file_b_id",
            "similarity_results",
            ["file_b_id"],
        )


def downgrade():
    op.drop_index("ix_similarity_results_file_b_id", table_name="similarity_results")
    op.drop_index("ix_similarity_results_file_a_id", table_name="similarity_results")
    op.drop_index("ix_files_task_id", table_name="files")
    op.drop_index("ix_plagiarism_tasks_deleted_at", table_name="plagiarism_tasks")
    op.drop_index("ix_plagiarism_tasks_assignment_id", table_name="plagiarism_tasks")
