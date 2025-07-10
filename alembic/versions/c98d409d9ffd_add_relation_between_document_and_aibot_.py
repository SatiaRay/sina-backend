"""add relation between document and aibot for multiple agent option

Revision ID: c98d409d9ffd
Revises: 84896c3731bf
Create Date: 2025-07-07 21:11:14.425989

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c98d409d9ffd'
down_revision: Union[str, None] = '84896c3731bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
