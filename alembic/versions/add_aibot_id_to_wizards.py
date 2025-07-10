"""add_aibot_id_to_wizards

Revision ID: add_aibot_id_to_wizards
Revises: 283bb218c7ea
Create Date: 2025-01-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_aibot_id_to_wizards'
down_revision: Union[str, None] = '283bb218c7ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add aibot_id column to wizards table
    op.add_column('wizards', sa.Column('aibot_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'wizards', 'aibots', ['aibot_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Remove foreign key constraint
    op.drop_constraint(None, 'wizards', type_='foreignkey')
    # Remove aibot_id column
    op.drop_column('wizards', 'aibot_id') 