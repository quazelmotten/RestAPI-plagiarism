"""Add is_confirmed column to files table for plagiarism review workflow

Revision ID: 9876543210ab
Revises: 2026-04-08_fix_unique_constraints_001
Create Date: 2026-04-08 03:00:00.000000

"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "9876543210ab"
down_revision = "fix_unique_constraints_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        text(
            "ALTER TABLE files ADD COLUMN IF NOT EXISTS is_confirmed BOOLEAN DEFAULT false NOT NULL"
        )
    )
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_files_is_confirmed ON files (is_confirmed)"))


def downgrade():
    op.execute(text("DROP INDEX IF EXISTS ix_files_is_confirmed"))
    op.execute(text("ALTER TABLE files DROP COLUMN IF EXISTS is_confirmed"))
