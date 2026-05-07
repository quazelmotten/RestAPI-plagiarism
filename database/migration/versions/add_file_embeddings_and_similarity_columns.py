"""Add file_embeddings table and embedding columns to similarity_results.

Revision ID: a1b2c3d4e5f8
Revises: 9876543210ab (add_file_is_confirmed)
Create Date: 2026-05-07 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import LargeBinary
from sqlalchemy.dialects.postgresql import JSONB, UUID

# Revision identifiers
revision = "a1b2c3d4e5f8"
down_revision = "a5152c7df72e"  # Create linear chain after add_reviewed_by
branch_labels = None
depends_on = None


def upgrade():
    """Add file_embeddings table and new columns to similarity_results."""

    # Create file_embeddings table
    op.create_table(
        "file_embeddings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("file_hash", sa.String(64), unique=True, index=True, nullable=False),
        sa.Column("embedding", LargeBinary, nullable=False),
        sa.Column("embedding_dim", sa.Integer(), server_default="256", nullable=False),
        sa.Column("model_version", sa.String(50), server_default="F2LLM-v2-80M", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create index on file_hash for fast lookups
    op.create_index("ix_file_embeddings_file_hash", "file_embeddings", ["file_hash"], unique=True)

    # Add new columns to similarity_results
    op.add_column("similarity_results", sa.Column("embedding_similarity", sa.Float(), nullable=True))
    op.add_column("similarity_results", sa.Column("type_confidence", JSONB(), nullable=True))

    # Create index on embedding_similarity for queries
    op.create_index(
        "ix_similarity_results_embedding_sim",
        "similarity_results",
        ["embedding_similarity"],
        postgresql_where=sa.text("embedding_similarity IS NOT NULL"),
    )


def downgrade():
    """Remove file_embeddings table and new columns."""

    # Drop indexes
    op.drop_index("ix_similarity_results_embedding_sim", table_name="similarity_results")
    op.drop_index("ix_file_embeddings_file_hash", table_name="file_embeddings")

    # Drop new columns from similarity_results
    op.drop_column("similarity_results", "type_confidence")
    op.drop_column("similarity_results", "embedding_similarity")

    # Drop file_embeddings table
    op.drop_table("file_embeddings")
