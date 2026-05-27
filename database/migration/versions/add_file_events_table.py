"""Add file_events table for audit log

Revision ID: add_file_events_table
Revises: add_task_cleanup_indexes
Create Date: 2026-05-24

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "add_file_events_table"
down_revision = "add_review_queue_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "file_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("assignment_id", UUID(as_uuid=True), sa.ForeignKey("assignments.id"), nullable=True, index=True),
        sa.Column("task_id", UUID(as_uuid=True), sa.ForeignKey("plagiarism_tasks.id"), nullable=True, index=True),
        sa.Column("event_type", sa.String(50), nullable=False, index=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("file_events")
