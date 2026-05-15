"""add chunks table

Revision ID: fc80c83e59fe
Revises: c84fa5188aed
Create Date: 2026-05-15 00:22:50.087399

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fc80c83e59fe"
down_revision: Union[str, Sequence[str], None] = "c84fa5188aed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("video_id", sa.Integer(), nullable=False),
        sa.Column("phrase", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("phrase_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("prompts", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("video_id", "phrase_key", name="uq_chunks_video_phrase"),
    )
    op.create_index(op.f("ix_chunks_phrase_key"), "chunks", ["phrase_key"], unique=False)
    op.create_index(op.f("ix_chunks_video_id"), "chunks", ["video_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_chunks_video_id"), table_name="chunks")
    op.drop_index(op.f("ix_chunks_phrase_key"), table_name="chunks")
    op.drop_table("chunks")
