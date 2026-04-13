"""agregar preferred_browsers_json a bot_global_config

Revision ID: agregar_preferred_browsers_json
Revises: agregar_config_dominios_servidor
Create Date: 2026-04-13 18:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'agregar_preferred_browsers_json'
down_revision = 'agregar_config_dominios_servidor'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c['name'] for c in inspector.get_columns('bot_global_config')]
    if 'preferred_browsers_json' not in cols:
        op.add_column(
            'bot_global_config',
            sa.Column('preferred_browsers_json', sa.Text(), nullable=True),
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c['name'] for c in inspector.get_columns('bot_global_config')]
    if 'preferred_browsers_json' in cols:
        op.drop_column('bot_global_config', 'preferred_browsers_json')
