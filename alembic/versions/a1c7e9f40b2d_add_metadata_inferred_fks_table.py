"""add_metadata_inferred_fks_table

Revision ID: a1c7e9f40b2d
Revises: 8786cdcd3fa3
Create Date: 2026-06-19 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1c7e9f40b2d'
down_revision: Union[str, Sequence[str], None] = '8786cdcd3fa3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'metadata_inferred_fks',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('data_source_id', sa.Uuid(), nullable=False),
        sa.Column('source_schema', sa.String(length=100), nullable=False),
        sa.Column('source_table', sa.String(length=100), nullable=False),
        sa.Column('source_column', sa.String(length=100), nullable=False),
        sa.Column('target_schema', sa.String(length=100), nullable=False),
        sa.Column('target_table', sa.String(length=100), nullable=False),
        sa.Column('target_column', sa.String(length=100), nullable=False),
        sa.Column('overlap_rate', sa.Float(), nullable=False),
        sa.Column('name_similarity', sa.Float(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('source', sa.String(length=30), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['data_source_id'], ['data_sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'data_source_id',
            'source_table',
            'source_column',
            'target_table',
            'target_column',
            name='uq_metadata_inferred_fks_pair',
        ),
    )
    op.create_index(
        'ix_metadata_inferred_fks_data_source_id',
        'metadata_inferred_fks',
        ['data_source_id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_metadata_inferred_fks_data_source_id', table_name='metadata_inferred_fks')
    op.drop_table('metadata_inferred_fks')
