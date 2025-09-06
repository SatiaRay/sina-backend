"""merge heads

Revision ID: 72051cc2c81b
Revises: 25eec75f3857, 76b2aa7b7616
Create Date: 2025-09-06 02:56:39.740123

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '72051cc2c81b'
down_revision: Union[str, None] = ('25eec75f3857', '76b2aa7b7616')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
