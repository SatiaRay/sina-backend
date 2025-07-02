"""add operator to user_type_enum

Revision ID: 0a51dba90d43
Revises: 7a8ed9cbd5db
Create Date: 2025-07-01 00:22:58.447720

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '0a51dba90d43'
down_revision: Union[str, None] = '7a8ed9cbd5db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'operator' to the user_type_enum in MySQL
    op.execute("ALTER TABLE users MODIFY COLUMN user_type ENUM('admin', 'supporter', 'customer', 'operator') NOT NULL DEFAULT 'customer';")

def downgrade() -> None:
    # Remove 'operator' from the user_type_enum in MySQL
    op.execute("ALTER TABLE users MODIFY COLUMN user_type ENUM('admin', 'supporter', 'customer') NOT NULL DEFAULT 'customer';")
