"""Remove active column from products table

Revision ID: 017f5080bc05
Revises: 001_initial
Create Date: 2025-11-26 18:35:15.897489

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '017f5080bc05'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the active column from products table
    op.drop_column('products', 'active')


def downgrade() -> None:
    # Re-add the active column if needed for rollback
    op.add_column('products', sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()))

