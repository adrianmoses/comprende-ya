"""add_frase_exercise_table

Revision ID: 2e27141dd6c1
Revises: cd3ded574f5e
Create Date: 2025-12-13 21:27:53.785274

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '2e27141dd6c1'
down_revision: Union[str, Sequence[str], None] = 'cd3ded574f5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'frase_exercise',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('video_id', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.Float(), nullable=False),
        sa.Column('end_time', sa.Float(), nullable=False),
        sa.Column('original_transcript_text', sa.String(), nullable=False),
        sa.Column('exercise_text', sa.String(), nullable=False),
        sa.Column('answers', sa.String(), nullable=False),  # JSON string
        sa.Column('hints', sa.String(), nullable=False),  # JSON string
        sa.Column('difficulty', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_frase_exercise_video_id', 'frase_exercise', ['video_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_frase_exercise_video_id', table_name='frase_exercise')
    op.drop_table('frase_exercise')
