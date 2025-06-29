"""add_workspace_tenancy_to_shared_models

Revision ID: bee5b09b86f7
Revises: 31c875867116
Create Date: 2025-06-29 02:34:56.264318

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = 'bee5b09b86f7'
down_revision: Union[str, None] = '31c875867116'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Check if workspace_id column exists before adding it
    connection = op.get_bind()
    
    # Add workspace_id column to wizards table (if not exists)
    inspector = sa.inspect(connection)
    wizards_columns = [col['name'] for col in inspector.get_columns('wizards')]
    if 'workspace_id' not in wizards_columns:
        op.add_column('wizards', sa.Column('workspace_id', sa.Integer(), nullable=True))
        op.create_index(op.f('ix_wizards_workspace_id'), 'wizards', ['workspace_id'], unique=False)
        op.create_foreign_key(None, 'wizards', 'workspaces', ['workspace_id'], ['id'])
    
    # Add workspace_id column to crawled_domains table (if not exists)
    crawled_domains_columns = [col['name'] for col in inspector.get_columns('crawled_domains')]
    if 'workspace_id' not in crawled_domains_columns:
        op.add_column('crawled_domains', sa.Column('workspace_id', sa.Integer(), nullable=True))
        op.create_index(op.f('ix_crawled_domains_workspace_id'), 'crawled_domains', ['workspace_id'], unique=False)
        op.create_foreign_key(None, 'crawled_domains', 'workspaces', ['workspace_id'], ['id'])
    
    # Remove unique constraint from domain column in crawled_domains (if exists)
    try:
        op.drop_constraint('crawled_domains_domain_key', 'crawled_domains', type_='unique')
    except:
        pass  # Constraint might not exist
    
    # Add workspace_id column to crawl_jobs table
    crawl_jobs_columns = [col['name'] for col in inspector.get_columns('crawl_jobs')]
    if 'workspace_id' not in crawl_jobs_columns:
        op.add_column('crawl_jobs', sa.Column('workspace_id', sa.Integer(), nullable=True))
        op.create_index(op.f('ix_crawl_jobs_workspace_id'), 'crawl_jobs', ['workspace_id'], unique=False)
        op.create_foreign_key(None, 'crawl_jobs', 'workspaces', ['workspace_id'], ['id'])
    
    # Remove unique constraint from job_id column in crawl_jobs (if exists)
    try:
        op.drop_constraint('crawl_jobs_job_id_key', 'crawl_jobs', type_='unique')
    except:
        pass  # Constraint might not exist
    
    # Add workspace_id column to documents table
    documents_columns = [col['name'] for col in inspector.get_columns('documents')]
    if 'workspace_id' not in documents_columns:
        op.add_column('documents', sa.Column('workspace_id', sa.Integer(), nullable=True))
        op.create_index(op.f('ix_documents_workspace_id'), 'documents', ['workspace_id'], unique=False)
        op.create_foreign_key(None, 'documents', 'workspaces', ['workspace_id'], ['id'])
    
    # Add workspace_id column to workflows table
    workflows_columns = [col['name'] for col in inspector.get_columns('workflows')]
    if 'workspace_id' not in workflows_columns:
        op.add_column('workflows', sa.Column('workspace_id', sa.Integer(), nullable=True))
        op.create_index(op.f('ix_workflows_workspace_id'), 'workflows', ['workspace_id'], unique=False)
        op.create_foreign_key(None, 'workflows', 'workspaces', ['workspace_id'], ['id'])
    
    # Remove unique constraint from name column in workflows (if exists)
    try:
        op.drop_constraint('workflows_name_key', 'workflows', type_='unique')
    except:
        pass  # Constraint might not exist
    
    # Add workspace_id column to instructions table
    instructions_columns = [col['name'] for col in inspector.get_columns('instructions')]
    if 'workspace_id' not in instructions_columns:
        op.add_column('instructions', sa.Column('workspace_id', sa.Integer(), nullable=True))
        op.create_index(op.f('ix_instructions_workspace_id'), 'instructions', ['workspace_id'], unique=False)
        op.create_foreign_key(None, 'instructions', 'workspaces', ['workspace_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Remove workspace_id columns and constraints
    try:
        op.drop_constraint(None, 'instructions', type_='foreignkey')
        op.drop_index(op.f('ix_instructions_workspace_id'), table_name='instructions')
        op.drop_column('instructions', 'workspace_id')
    except:
        pass
    
    try:
        op.drop_constraint(None, 'workflows', type_='foreignkey')
        op.drop_index(op.f('ix_workflows_workspace_id'), table_name='workflows')
        op.drop_column('workflows', 'workspace_id')
        op.create_unique_constraint('workflows_name_key', 'workflows', ['name'])
    except:
        pass
    
    try:
        op.drop_constraint(None, 'documents', type_='foreignkey')
        op.drop_index(op.f('ix_documents_workspace_id'), table_name='documents')
        op.drop_column('documents', 'workspace_id')
    except:
        pass
    
    try:
        op.drop_constraint(None, 'crawl_jobs', type_='foreignkey')
        op.drop_index(op.f('ix_crawl_jobs_workspace_id'), table_name='crawl_jobs')
        op.drop_column('crawl_jobs', 'workspace_id')
        op.create_unique_constraint('crawl_jobs_job_id_key', 'crawl_jobs', ['job_id'])
    except:
        pass
    
    try:
        op.drop_constraint(None, 'crawled_domains', type_='foreignkey')
        op.drop_index(op.f('ix_crawled_domains_workspace_id'), table_name='crawled_domains')
        op.drop_column('crawled_domains', 'workspace_id')
        op.create_unique_constraint('crawled_domains_domain_key', 'crawled_domains', ['domain'])
    except:
        pass
    
    try:
        op.drop_constraint(None, 'wizards', type_='foreignkey')
        op.drop_index(op.f('ix_wizards_workspace_id'), table_name='wizards')
        op.drop_column('wizards', 'workspace_id')
    except:
        pass
