"""add_aibot_id_to_documents

Revision ID: 283bb218c7ea
Revises: c98d409d9ffd
Create Date: 2025-07-07 21:25:45.565494

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '283bb218c7ea'
down_revision: Union[str, None] = 'c98d409d9ffd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add aibot_id column to documents table
    op.add_column('documents', sa.Column('aibot_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'documents', 'aibots', ['aibot_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Remove foreign key constraint
    op.drop_constraint(None, 'documents', type_='foreignkey')
    # Remove aibot_id column
    op.drop_column('documents', 'aibot_id')
