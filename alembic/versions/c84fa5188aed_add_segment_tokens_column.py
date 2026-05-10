"""add segment tokens column

Revision ID: c84fa5188aed
Revises: 929145c0af7d
Create Date: 2026-05-09 22:03:10.050434

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c84fa5188aed"
down_revision: Union[str, Sequence[str], None] = "929145c0af7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "video_segments",
        sa.Column("tokens", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("video_segments", "tokens")
