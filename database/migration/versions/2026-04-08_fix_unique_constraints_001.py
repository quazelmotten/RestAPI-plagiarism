"""Convert unique constraints to partial indexes for soft delete

This migration:
1. Drops existing unique constraints on assignments.name and subjects.name
2. Creates partial unique indexes that only apply where deleted_at IS NULL
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'fix_unique_constraints_001'
down_revision = 'soft_delete_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the existing unique constraint on assignments.name
    # The constraint name is likely 'assignments_name_key' based on the error
    op.drop_constraint('assignments_name_key', 'assignments', type_='unique')

    # Drop the existing unique constraint on subjects.name
    op.drop_constraint('subjects_name_key', 'subjects', type_='unique')

    # Create partial unique indexes for non-deleted records only
    op.create_index(
        'ix_assignments_name_not_deleted',
        'assignments',
        ['name'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL')
    )

    op.create_index(
        'ix_subjects_name_not_deleted',
        'subjects',
        ['name'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL')
    )


def downgrade() -> None:
    # Remove partial indexes
    op.drop_index('ix_assignments_name_not_deleted', table_name='assignments')
    op.drop_index('ix_subjects_name_not_deleted', table_name='subjects')

    # Restore original unique constraints
    op.create_unique_constraint('assignments_name_key', 'assignments', ['name'])
    op.create_unique_constraint('subjects_name_key', 'subjects', ['name'])
