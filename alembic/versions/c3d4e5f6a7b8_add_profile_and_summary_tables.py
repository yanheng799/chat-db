"""add_profile_and_summary_tables

Revision ID: c3d4e5f6a7b8
Revises: b2d3e4f5a6c7
Create Date: 2026-06-19 00:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2d3e4f5a6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('conversation_summaries',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('session_id', sa.String(64), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_table('user_profiles',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('session_id', sa.String(64), nullable=False, unique=True),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('skill_level', sa.String(20), nullable=False, server_default='beginner'),
        sa.Column('time_preference', sa.String(10), nullable=False, server_default='30d'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_table('user_table_preferences',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('session_id', sa.String(64), nullable=False),
        sa.Column('table_name', sa.String(100), nullable=False),
        sa.Column('query_count', sa.Integer(), nullable=False, server_default='1'),
        sa.UniqueConstraint('session_id', 'table_name', name='uq_user_table_pref'),
    )
    op.create_table('user_term_mappings',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('session_id', sa.String(64), nullable=False),
        sa.Column('user_term', sa.String(200), nullable=False),
        sa.Column('corrected_term', sa.String(200), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('user_term_mappings')
    op.drop_table('user_table_preferences')
    op.drop_table('user_profiles')
    op.drop_table('conversation_summaries')
