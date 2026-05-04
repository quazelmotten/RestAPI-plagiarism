"""Add username column to users table

Revision ID: add_user_username_column
Revises: add_api_keys_table
Create Date: 2026-05-04 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "add_user_username_column"
down_revision = "add_api_keys_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(100), nullable=True))
    op.create_index("ix_users_username", "users", ["username"])


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")