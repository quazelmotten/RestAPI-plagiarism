"""Add user_id column to file_events table

Revision ID: add_user_id_to_file_events
Revises: add_file_events_table
Create Date: 2026-05-25

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "add_user_id_to_file_events"
down_revision = "add_file_events_table"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "file_events",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True, index=True),
    )


def downgrade():
    op.drop_column("file_events", "user_id")
