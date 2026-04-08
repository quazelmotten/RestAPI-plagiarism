"""Add indexes to improve query performance for assignment full endpoint

Revision ID: cfe1bb1b6a5c
Revises: a1b2c3d4e5f6
Create Date: 2026-04-05 04:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "cfe1bb1b6a5c"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    # Index for filtering tasks by assignment
    op.create_index("ix_plagiarismtask_assignment_id", "plagiarism_tasks", ["assignment_id"])
    # Index for joining files to tasks
    op.create_index("ix_file_task_id", "files", ["task_id"])
    # Indexes for filtering similarity results by task
    op.create_index("ix_similarityresult_task_id", "similarity_results", ["task_id"])
    # Indexes for file_a and file_b joins (used in max similarity queries)
    op.create_index("ix_similarityresult_file_a_id", "similarity_results", ["file_a_id"])
    op.create_index("ix_similarityresult_file_b_id", "similarity_results", ["file_b_id"])


def downgrade():
    op.drop_index("ix_similarityresult_file_b_id", table_name="similarity_results")
    op.drop_index("ix_similarityresult_file_a_id", table_name="similarity_results")
    op.drop_index("ix_similarityresult_task_id", table_name="similarity_results")
    op.drop_index("ix_file_task_id", table_name="files")
    op.drop_index("ix_plagiarismtask_assignment_id", table_name="plagiarism_tasks")
