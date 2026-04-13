"""agregar configuracion global bot y catalogo navegadores

Revision ID: agregar_config_global_bot
Revises: agregar_preferred_browser
Create Date: 2026-04-13 11:05:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'agregar_config_global_bot'
down_revision = 'agregar_preferred_browser'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'bot_global_config' not in existing_tables:
        op.create_table(
            'bot_global_config',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('preferred_browser', sa.String(length=100), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id')
        )
        print("[OK] Tabla bot_global_config creada")
    else:
        print("[INFO] Tabla bot_global_config ya existe, omitiendo")

    if 'bot_browser_catalog' not in existing_tables:
        op.create_table(
            'bot_browser_catalog',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('browser_name', sa.String(length=100), nullable=False),
            sa.Column('last_seen', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'browser_name', name='uq_user_browser_name')
        )
        op.create_index('idx_bot_browser_catalog_user_id', 'bot_browser_catalog', ['user_id'], unique=False)
        print("[OK] Tabla bot_browser_catalog creada")
    else:
        print("[INFO] Tabla bot_browser_catalog ya existe, omitiendo")


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'bot_browser_catalog' in existing_tables:
        op.drop_index('idx_bot_browser_catalog_user_id', table_name='bot_browser_catalog')
        op.drop_table('bot_browser_catalog')
        print("[OK] Tabla bot_browser_catalog eliminada")
    else:
        print("[INFO] Tabla bot_browser_catalog no existe, omitiendo")

    if 'bot_global_config' in existing_tables:
        op.drop_table('bot_global_config')
        print("[OK] Tabla bot_global_config eliminada")
    else:
        print("[INFO] Tabla bot_global_config no existe, omitiendo")
