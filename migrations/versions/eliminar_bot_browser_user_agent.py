"""eliminar tabla bot_browser_user_agent (UA va por cuenta)

Revision ID: eliminar_bot_browser_user_agent
Revises: agregar_creator_time_global_config
Create Date: 2026-05-04 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'eliminar_bot_browser_user_agent'
down_revision = 'agregar_creator_time_global_config'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    if 'bot_browser_user_agent' in existing_tables:
        op.drop_index('idx_bot_browser_user_agent_user_id', table_name='bot_browser_user_agent')
        op.drop_table('bot_browser_user_agent')


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    if 'bot_browser_user_agent' not in existing_tables:
        op.create_table(
            'bot_browser_user_agent',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('browser_name', sa.String(length=100), nullable=False),
            sa.Column('user_agent', sa.Text(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'browser_name', name='uq_user_browser_user_agent'),
        )
        op.create_index(
            'idx_bot_browser_user_agent_user_id',
            'bot_browser_user_agent',
            ['user_id'],
            unique=False,
        )
