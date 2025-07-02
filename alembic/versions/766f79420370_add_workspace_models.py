"""add_workspace_models

Revision ID: 766f79420370
Revises: 625036065608
Create Date: 2025-06-29 00:51:48.743310

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '766f79420370'
down_revision: Union[str, None] = '625036065608'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
