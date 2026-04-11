"""remove_h5p_content

Revision ID: 375de2969af7
Revises: 0ec4b4ee0c36
Create Date: 2025-12-06 16:25:44.650476

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '375de2969af7'
down_revision: Union[str, Sequence[str], None] = '0ec4b4ee0c36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('videos', 'h5p_content')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('videos', sa.Column('h5p_content', sa.JSON(), nullable=True))
