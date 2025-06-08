"""Delete workflows which its flow None

Revision ID: 8c0a9e0458b2
Revises: 3a00a37fe703
Create Date: 2025-06-08 04:26:38.244675

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c0a9e0458b2'
down_revision: Union[str, None] = '3a00a37fe703'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    from alembic import op
    op.execute("DELETE FROM workflows WHERE flow IS NULL OR flow = '[]' OR flow = ''")
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
