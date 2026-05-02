"""Change h5p_content type to JSON

Revision ID: c6440d9b9453
Revises: 6554f5747ad9
Create Date: 2025-11-09 21:04:23.346943

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c6440d9b9453"
down_revision: Union[str, Sequence[str], None] = "6554f5747ad9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite stores JSON as TEXT and doesn't support `ALTER COLUMN ... TYPE`.
    # The h5p_content column is dropped entirely two migrations later
    # (375de2969af7), so on SQLite this migration is a no-op for end state.
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    op.alter_column(
        "videos",
        "h5p_content",
        existing_type=sa.VARCHAR(),
        type_=sa.JSON(),
        existing_nullable=True,
        postgresql_using="h5p_content::json",
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    op.alter_column(
        "videos", "h5p_content", existing_type=sa.JSON(), type_=sa.VARCHAR(), existing_nullable=True
    )
