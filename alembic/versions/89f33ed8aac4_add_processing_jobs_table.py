"""add_processing_jobs_table

Revision ID: 89f33ed8aac4
Revises: 2e27141dd6c1
Create Date: 2026-05-02 19:23:22.351859

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '89f33ed8aac4'
down_revision: Union[str, Sequence[str], None] = '2e27141dd6c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'processing_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('flow_run_id', sqlmodel.sql.sqltypes.AutoString(length=36), nullable=False),
        sa.Column('youtube_url', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('youtube_video_id', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False, server_default='PENDING'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('video_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','COMPLETED','FAILED')",
            name='ck_processing_jobs_status',
        ),
    )
    op.create_index(
        op.f('ix_processing_jobs_flow_run_id'),
        'processing_jobs',
        ['flow_run_id'],
        unique=True,
    )
    op.create_index(
        op.f('ix_processing_jobs_youtube_video_id'),
        'processing_jobs',
        ['youtube_video_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_processing_jobs_status'),
        'processing_jobs',
        ['status'],
        unique=False,
    )
    op.create_index(
        op.f('ix_processing_jobs_created_at'),
        'processing_jobs',
        ['created_at'],
        unique=False,
    )
    op.create_index(
        op.f('ix_processing_jobs_video_id'),
        'processing_jobs',
        ['video_id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_processing_jobs_video_id'), table_name='processing_jobs')
    op.drop_index(op.f('ix_processing_jobs_created_at'), table_name='processing_jobs')
    op.drop_index(op.f('ix_processing_jobs_status'), table_name='processing_jobs')
    op.drop_index(op.f('ix_processing_jobs_youtube_video_id'), table_name='processing_jobs')
    op.drop_index(op.f('ix_processing_jobs_flow_run_id'), table_name='processing_jobs')
    op.drop_table('processing_jobs')
