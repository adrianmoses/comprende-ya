"""add phrase_autopsy table

Revision ID: 929145c0af7d
Revises: 89f33ed8aac4
Create Date: 2026-05-09 14:08:53.962617

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '929145c0af7d'
down_revision: Union[str, Sequence[str], None] = '89f33ed8aac4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'phrase_autopsy',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('video_id', sa.Integer(), nullable=False),
        sa.Column('phrase', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('phrase_key', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('start_time', sa.Float(), nullable=False),
        sa.Column('register', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('grammar', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('natural_notes', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('video_id', 'phrase_key', name='uq_phrase_autopsy_video_key'),
    )
    op.create_index(
        op.f('ix_phrase_autopsy_phrase_key'),
        'phrase_autopsy',
        ['phrase_key'],
        unique=False,
    )
    op.create_index(
        op.f('ix_phrase_autopsy_video_id'),
        'phrase_autopsy',
        ['video_id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_phrase_autopsy_video_id'), table_name='phrase_autopsy')
    op.drop_index(op.f('ix_phrase_autopsy_phrase_key'), table_name='phrase_autopsy')
    op.drop_table('phrase_autopsy')
