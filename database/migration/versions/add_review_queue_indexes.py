"""Add indexes for review queue and cleanup performance

Revision ID: add_review_queue_indexes
Revises: add_task_name_and_language
Create Date: 2026-05-21 00:00:00.000000

"""

from alembic import op

revision = "add_review_queue_indexes"
down_revision = "add_task_name_and_language"
branch_labels = None
depends_on = None


def upgrade():
    # Index for filtering review queue by disposition (most common filter)
    op.create_index(
        "ix_similarityresult_review_disposition",
        "similarity_results",
        ["review_disposition"],
    )

    # Composite index for review queue: filter by disposition, sort by similarity
    op.create_index(
        "ix_similarityresult_disposition_similarity",
        "similarity_results",
        ["review_disposition", "ast_similarity"],
    )

    # Index for filtering tasks by status (used in upload list)
    op.create_index(
        "ix_plagiarismtask_status",
        "plagiarism_tasks",
        ["status"],
    )

    # Index for filtering files by task and language
    op.create_index(
        "ix_file_task_language",
        "files",
        ["task_id", "language"],
    )

    # Index for orphaned task queries
    op.create_index(
        "ix_plagiarismtask_deleted_at",
        "plagiarism_tasks",
        ["deleted_at"],
    )

    # Index for assignment-scoped review queue
    op.create_index(
        "ix_plagiarismtask_assignment_status",
        "plagiarism_tasks",
        ["assignment_id", "status"],
    )


def downgrade():
    op.drop_index("ix_plagiarismtask_assignment_status", table_name="plagiarism_tasks")
    op.drop_index("ix_plagiarismtask_deleted_at", table_name="plagiarism_tasks")
    op.drop_index("ix_file_task_language", table_name="files")
    op.drop_index("ix_plagiarismtask_status", table_name="plagiarism_tasks")
    op.drop_index("ix_similarityresult_disposition_similarity", table_name="similarity_results")
    op.drop_index("ix_similarityresult_review_disposition", table_name="similarity_results")
