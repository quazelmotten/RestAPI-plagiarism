"""Add composite indexes for bulk operations

Revision ID: add_bulk_operation_indexes
Revises: add_user_lockout_session_version
Create Date: 2026-05-01 12:00:00.000000

"""

from alembic import op
from sqlalchemy import text

revision = "add_bulk_operation_indexes"
down_revision = "add_user_lockout_session_version"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    result = conn.execute(
        text("SELECT indexname FROM pg_indexes WHERE indexname = 'ix_files_is_confirmed'")
    )
    if not result.fetchone():
        op.create_index(
            "ix_files_is_confirmed",
            "files",
            ["is_confirmed"],
        )

    result = conn.execute(
        text("SELECT indexname FROM pg_indexes WHERE indexname = 'ix_similarity_results_task_disposition_threshold'")
    )
    if not result.fetchone():
        op.create_index(
            "ix_similarity_results_task_disposition_threshold",
            "similarity_results",
            ["task_id", "review_disposition", "ast_similarity"],
        )


def downgrade():
    op.drop_index("ix_files_is_confirmed", table_name="files")
    op.drop_index(
        "ix_similarity_results_task_disposition_threshold",
        table_name="similarity_results",
    )