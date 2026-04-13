"""Add role column back to users table (viewer/reviewer/admin).

Revision ID: add_role_back_001
Revises: u_auth_simple_subj_acc
Create Date: 2026-04-12 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "add_role_back_001"
down_revision = "u_auth_simple_subj_acc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add role column with default 'viewer'
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=20), nullable=False, server_default="viewer"),
    )
    # Map existing admin rows (is_global_admin) to admin role
    op.execute("UPDATE users SET role = 'admin' WHERE is_global_admin = true")
    # Create index for role lookups
    op.create_index("ix_users_role", "users", ["role"])


def downgrade() -> None:
    op.drop_index("ix_users_role", table_name="users")
    op.drop_column("users", "role")
