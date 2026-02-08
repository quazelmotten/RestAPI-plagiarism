"""Convert varchar id columns to uuid type

Revision ID: 2a8c9e1f45b2
Revises: 1d95f3a38336
Create Date: 2026-02-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2a8c9e1f45b2'
down_revision = '1d95f3a38336'
branch_labels = None
depends_on = None

def upgrade():
    # Drop foreign key constraints first
    op.drop_constraint('files_task_id_fkey', 'files', type_='foreignkey')
    op.drop_constraint('similarity_results_task_id_fkey', 'similarity_results', type_='foreignkey')
    op.drop_constraint('similarity_results_file_a_id_fkey', 'similarity_results', type_='foreignkey')
    op.drop_constraint('similarity_results_file_b_id_fkey', 'similarity_results', type_='foreignkey')
    
    # Convert plagiarism_tasks.id
    op.execute('ALTER TABLE plagiarism_tasks ALTER COLUMN id TYPE uuid USING id::uuid')
    
    # Convert files columns
    op.execute('ALTER TABLE files ALTER COLUMN id TYPE uuid USING id::uuid')
    op.execute('ALTER TABLE files ALTER COLUMN task_id TYPE uuid USING task_id::uuid')
    
    # Convert similarity_results columns
    op.execute('ALTER TABLE similarity_results ALTER COLUMN id TYPE uuid USING id::uuid')
    op.execute('ALTER TABLE similarity_results ALTER COLUMN task_id TYPE uuid USING task_id::uuid')
    op.execute('ALTER TABLE similarity_results ALTER COLUMN file_a_id TYPE uuid USING file_a_id::uuid')
    op.execute('ALTER TABLE similarity_results ALTER COLUMN file_b_id TYPE uuid USING file_b_id::uuid')
    
    # Recreate foreign key constraints
    op.create_foreign_key('files_task_id_fkey', 'files', 'plagiarism_tasks', ['task_id'], ['id'])
    op.create_foreign_key('similarity_results_task_id_fkey', 'similarity_results', 'plagiarism_tasks', ['task_id'], ['id'])
    op.create_foreign_key('similarity_results_file_a_id_fkey', 'similarity_results', 'files', ['file_a_id'], ['id'])
    op.create_foreign_key('similarity_results_file_b_id_fkey', 'similarity_results', 'files', ['file_b_id'], ['id'])

def downgrade():
    # Drop foreign key constraints
    op.drop_constraint('files_task_id_fkey', 'files', type_='foreignkey')
    op.drop_constraint('similarity_results_task_id_fkey', 'similarity_results', type_='foreignkey')
    op.drop_constraint('similarity_results_file_a_id_fkey', 'similarity_results', type_='foreignkey')
    op.drop_constraint('similarity_results_file_b_id_fkey', 'similarity_results', type_='foreignkey')
    
    # Convert back to varchar
    op.execute('ALTER TABLE similarity_results ALTER COLUMN file_b_id TYPE varchar(36)')
    op.execute('ALTER TABLE similarity_results ALTER COLUMN file_a_id TYPE varchar(36)')
    op.execute('ALTER TABLE similarity_results ALTER COLUMN task_id TYPE varchar(36)')
    op.execute('ALTER TABLE similarity_results ALTER COLUMN id TYPE varchar(36)')
    
    op.execute('ALTER TABLE files ALTER COLUMN task_id TYPE varchar(36)')
    op.execute('ALTER TABLE files ALTER COLUMN id TYPE varchar(36)')
    
    op.execute('ALTER TABLE plagiarism_tasks ALTER COLUMN id TYPE varchar(36)')
    
    # Recreate foreign key constraints
    op.create_foreign_key('files_task_id_fkey', 'files', 'plagiarism_tasks', ['task_id'], ['id'])
    op.create_foreign_key('similarity_results_task_id_fkey', 'similarity_results', 'plagiarism_tasks', ['task_id'], ['id'])
    op.create_foreign_key('similarity_results_file_a_id_fkey', 'similarity_results', 'files', ['file_a_id'], ['id'])
    op.create_foreign_key('similarity_results_file_b_id_fkey', 'similarity_results', 'files', ['file_b_id'], ['id'])
