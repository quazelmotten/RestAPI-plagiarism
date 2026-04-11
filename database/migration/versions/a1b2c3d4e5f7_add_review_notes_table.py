"""Add review_notes table for per-file annotations

Revision ID: a1b2c3d4e5f7
Revises: 9876543210ab
Create Date: 2026-04-10 00:00:00.000000

"""

from alembic import op
from sqlalchemy import text

revision = "a1b2c3d4e5f7"
down_revision = "9876543210ab"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        text("""
            CREATE TABLE IF NOT EXISTS review_notes (
                id UUID NOT NULL,
                file_id UUID NOT NULL,
                assignment_id UUID NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
                PRIMARY KEY (id),
                CONSTRAINT fk_review_notes_file_id FOREIGN KEY (file_id) REFERENCES files(id),
                CONSTRAINT fk_review_notes_assignment_id FOREIGN KEY (assignment_id) REFERENCES assignments(id)
            )
        """)
    )
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_review_notes_file_id ON review_notes (file_id)"))
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_review_notes_assignment_id ON review_notes (assignment_id)"
        )
    )


def downgrade():
    op.execute(text("DROP INDEX IF EXISTS ix_review_notes_assignment_id"))
    op.execute(text("DROP INDEX IF EXISTS ix_review_notes_file_id"))
    op.execute(text("DROP TABLE IF EXISTS review_notes"))
