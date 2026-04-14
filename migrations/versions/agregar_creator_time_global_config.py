"""agregar campos creator (ciclo/hora) a bot_global_config

Revision ID: agregar_creator_time_global_config
Revises: agregar_preferred_browsers_json
Create Date: 2026-04-14 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'agregar_creator_time_global_config'
down_revision = 'agregar_preferred_browsers_json'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c['name'] for c in inspector.get_columns('bot_global_config')]
    if 'creator_scheduled_time' not in cols:
        op.add_column(
            'bot_global_config',
            sa.Column('creator_scheduled_time', sa.String(length=16), nullable=True),
        )
    if 'creator_timezone' not in cols:
        op.add_column(
            'bot_global_config',
            sa.Column('creator_timezone', sa.String(length=255), nullable=True),
        )
    if 'creator_cycle_time_minutes' not in cols:
        op.add_column(
            'bot_global_config',
            sa.Column('creator_cycle_time_minutes', sa.Integer(), nullable=True),
        )
    if 'creator_time_config_type' not in cols:
        op.add_column(
            'bot_global_config',
            sa.Column('creator_time_config_type', sa.String(length=20), nullable=True),
        )
    if 'creator_accounts_per_cycle' not in cols:
        op.add_column(
            'bot_global_config',
            sa.Column('creator_accounts_per_cycle', sa.Integer(), nullable=True),
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c['name'] for c in inspector.get_columns('bot_global_config')]
    for name in (
        'creator_accounts_per_cycle',
        'creator_time_config_type',
        'creator_cycle_time_minutes',
        'creator_timezone',
        'creator_scheduled_time',
    ):
        if name in cols:
            op.drop_column('bot_global_config', name)
