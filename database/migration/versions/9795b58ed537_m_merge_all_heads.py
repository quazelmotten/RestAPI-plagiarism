"""-m merge all heads

Revision ID: 9795b58ed537
Revises: add_bulk_operation_indexes
Create Date: 2026-05-01 03:44:19.278167

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9795b58ed537'
down_revision = 'add_bulk_operation_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
