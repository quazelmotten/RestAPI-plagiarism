"""Convert unique constraints to partial indexes for soft delete

This migration:
1. Drops existing unique constraints on assignments.name and subjects.name
2. Creates partial unique indexes that only apply where deleted_at IS NULL
"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "fix_unique_constraints_001"
down_revision = "soft_delete_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make idempotent by using raw SQL with IF EXISTS
    # Drop the existing unique constraint on assignments.name if it exists
    op.execute(
        text("ALTER TABLE IF EXISTS assignments DROP CONSTRAINT IF EXISTS assignments_name_key")
    )

    # Drop the existing unique constraint on subjects.name if it exists
    op.execute(text("ALTER TABLE IF EXISTS subjects DROP CONSTRAINT IF EXISTS subjects_name_key"))

    # Create partial unique indexes for non-deleted records only (idempotent)
    op.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_assignments_name_not_deleted ON assignments (name) WHERE deleted_at IS NULL"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_subjects_name_not_deleted ON subjects (name) WHERE deleted_at IS NULL"
        )
    )


def downgrade() -> None:
    # Remove partial indexes
    op.drop_index("ix_assignments_name_not_deleted", table_name="assignments")
    op.drop_index("ix_subjects_name_not_deleted", table_name="subjects")

    # Restore original unique constraints
    op.create_unique_constraint("assignments_name_key", "assignments", ["name"])
    op.create_unique_constraint("subjects_name_key", "subjects", ["name"])
