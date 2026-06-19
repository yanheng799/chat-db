"""add_value_mapping_tables

Revision ID: b2d3e4f5a6c7
Revises: a1c7e9f40b2d
Create Date: 2026-06-19 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'b2d3e4f5a6c7'
down_revision: Union[str, Sequence[str], None] = 'a1c7e9f40b2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'value_enum_mappings',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('data_source_id', sa.Uuid(), sa.ForeignKey('data_sources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('table_name', sa.String(100), nullable=False),
        sa.Column('column_name', sa.String(100), nullable=False),
        sa.Column('value', sa.String(255), nullable=False),
        sa.Column('display', sa.String(255), nullable=False),
        sa.Column('aliases', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('data_source_id', 'table_name', 'column_name', 'value', name='uq_enum_mapping'),
    )
    op.create_table(
        'value_region_dict',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('data_source_id', sa.Uuid(), sa.ForeignKey('data_sources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(20), nullable=False),
        sa.Column('parent_code', sa.String(20), nullable=True),
        sa.Column('level', sa.String(20), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('aliases', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )
    op.create_table(
        'value_name_mappings',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('data_source_id', sa.Uuid(), sa.ForeignKey('data_sources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('short_name', sa.String(200), nullable=False),
        sa.Column('full_name', sa.String(500), nullable=False),
        sa.Column('target_table', sa.String(100), nullable=True),
        sa.Column('aliases', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('data_source_id', 'short_name', name='uq_name_mapping'),
    )


def downgrade() -> None:
    op.drop_table('value_name_mappings')
    op.drop_table('value_region_dict')
    op.drop_table('value_enum_mappings')
