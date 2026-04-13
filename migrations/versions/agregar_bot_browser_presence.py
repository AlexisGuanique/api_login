"""agregar tabla bot_browser_presence

Revision ID: agregar_bot_browser_presence
Revises: agregar_config_global_bot
Create Date: 2026-04-13 12:10:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'agregar_bot_browser_presence'
down_revision = 'agregar_config_global_bot'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'bot_browser_presence' not in existing_tables:
        op.create_table(
            'bot_browser_presence',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('bot_id', sa.Integer(), nullable=False),
            sa.Column('browser_name', sa.String(length=100), nullable=False),
            sa.Column('last_seen', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.ForeignKeyConstraint(['bot_id'], ['bot.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('bot_id', 'browser_name', name='uq_bot_browser_presence')
        )
        op.create_index('idx_bot_browser_presence_user_id', 'bot_browser_presence', ['user_id'], unique=False)
        op.create_index('idx_bot_browser_presence_bot_id', 'bot_browser_presence', ['bot_id'], unique=False)
        print("[OK] Tabla bot_browser_presence creada")
    else:
        print("[INFO] Tabla bot_browser_presence ya existe, omitiendo")


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'bot_browser_presence' in existing_tables:
        op.drop_index('idx_bot_browser_presence_bot_id', table_name='bot_browser_presence')
        op.drop_index('idx_bot_browser_presence_user_id', table_name='bot_browser_presence')
        op.drop_table('bot_browser_presence')
        print("[OK] Tabla bot_browser_presence eliminada")
    else:
        print("[INFO] Tabla bot_browser_presence no existe, omitiendo")
