"""Add ON DELETE CASCADE to file_events.task_id FK.

Revision ID: cascade_file_events_task_fk
Revises: add_user_id_to_file_events
Create Date: 2026-06-05

"""
from alembic import op


revision = "cascade_file_events_task_fk"
down_revision = "add_user_id_to_file_events"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "file_events_task_id_fkey",
        "file_events",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "file_events_task_id_fkey",
        "file_events",
        "plagiarism_tasks",
        ["task_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "file_events_assignment_id_fkey",
        "file_events",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "file_events_assignment_id_fkey",
        "file_events",
        "assignments",
        ["assignment_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    op.drop_constraint(
        "file_events_task_id_fkey",
        "file_events",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "file_events_task_id_fkey",
        "file_events",
        "plagiarism_tasks",
        ["task_id"],
        ["id"],
    )
    op.drop_constraint(
        "file_events_assignment_id_fkey",
        "file_events",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "file_events_assignment_id_fkey",
        "file_events",
        "assignments",
        ["assignment_id"],
        ["id"],
    )
