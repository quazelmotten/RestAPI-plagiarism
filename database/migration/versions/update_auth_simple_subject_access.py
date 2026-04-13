"""Update auth for simple subject-based access control

Revision ID: u_auth_simple_subj_acc
Revises: add_users_table_001
Create Date: 2026-04-12 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "u_auth_simple_subj_acc"
down_revision = "add_users_table_001"
branch_labels = None
depends_on = ["add_users_table_001", "d4e5f6a7b8c9"]


def upgrade() -> None:
    # Drop old role indexes
    op.drop_index("ix_users_role", table_name="users")

    # Remove old role column and add is_global_admin
    op.drop_column("users", "role")
    op.add_column(
        "users",
        sa.Column("is_global_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Create subject_access table
    op.create_table(
        "subject_access",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject_id", UUID(as_uuid=True), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column(
            "granted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("granted_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )

    # Create unique constraint
    op.create_unique_constraint(
        "uq_subject_access_user_subject", "subject_access", ["user_id", "subject_id"]
    )


def downgrade() -> None:
    # Drop subject_access table
    op.drop_table("subject_access")

    # Remove is_global_admin column
    op.drop_column("users", "is_global_admin")

    # Restore old role column
    op.add_column(
        "users", sa.Column("role", sa.String(20), nullable=False, server_default="viewer")
    )

    # Restore role index
    op.create_index("ix_users_role", "users", ["role"])
