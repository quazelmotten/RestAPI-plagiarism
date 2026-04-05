"""Add max_similarity column to files table

Revision ID: 3b7d5e9f2a1c
Revises: cfe1bb1b6a5c
Create Date: 2026-04-05 05:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3b7d5e9f2a1c"
down_revision = "cfe1bb1b6a5c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "files",
        sa.Column("max_similarity", sa.Float(), nullable=True, server_default=sa.text("0.0")),
    )

    op.execute("""
        UPDATE files
        SET max_similarity = sub.max_sim
        FROM (
            SELECT f.id, MAX(sr.ast_similarity) AS max_sim
            FROM files f
            LEFT JOIN similarity_results sr
                ON sr.file_a_id = f.id OR sr.file_b_id = f.id
            GROUP BY f.id
        ) sub
        WHERE files.id = sub.id
    """)


def downgrade():
    op.drop_column("files", "max_similarity")
