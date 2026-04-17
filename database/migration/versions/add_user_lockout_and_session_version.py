"""add user lockout and session version fields

Revision ID: add_user_lockout_session_version
Revises: update_auth_simple_subject_access
Create Date: 2026-04-13
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "add_user_lockout_session_version"
down_revision = "add_role_back_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new fields to users table
    op.add_column(
        "users",
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("users", sa.Column("lockout_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users", sa.Column("session_version", sa.Integer(), nullable=False, server_default="1")
    )


def downgrade() -> None:
    # Remove new fields
    op.drop_column("users", "session_version")
    op.drop_column("users", "lockout_until")
    op.drop_column("users", "failed_login_attempts")
