"""Add bulk_confirmed to review_disposition

Revision ID: add_bulk_confirmed_disposition
Revises: add_review_disposition_001
Create Date: 2026-04-11 00:00:00.000000

"""

from alembic import op

revision = "add_bulk_confirmed_disposition"
down_revision = "add_review_disposition_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE similarity_results
        DROP CONSTRAINT IF EXISTS review_disposition_check
    """)
    op.execute("""
        ALTER TABLE similarity_results
        ADD CONSTRAINT review_disposition_check
        CHECK (review_disposition IS NULL OR
               review_disposition IN ('plagiarism', 'clear', 'bulk_confirmed'))
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE similarity_results
        DROP CONSTRAINT IF EXISTS review_disposition_check
    """)
    op.execute("""
        ALTER TABLE similarity_results
        ADD CONSTRAINT review_disposition_check
        CHECK (review_disposition IS NULL OR
               review_disposition IN ('plagiarism', 'clear'))
    """)
