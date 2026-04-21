"""agregar configuracion global de logueador

Revision ID: agregar_config_logueador_global
Revises: agregar_creator_time_global_config
Create Date: 2026-04-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'agregar_config_logueador_global'
down_revision = 'agregar_creator_time_global_config'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'bot_logueador_config' in tables:
        print("[INFO] Tabla bot_logueador_config ya existe, omitiendo migracion")
        return

    op.create_table(
        'bot_logueador_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('iterations', sa.Integer(), nullable=False, server_default='16'),
        sa.Column('interval_seconds', sa.Integer(), nullable=False, server_default='7200'),
        sa.Column('user_agent', sa.Text(), nullable=True, server_default=''),
        sa.Column('ultra_email', sa.String(length=255), nullable=True),
        sa.Column('ultra_password', sa.String(length=255), nullable=True),
        sa.Column('use_local_accounts', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('ultra_login_mode', sa.String(length=20), nullable=False, server_default='sqlite'),
        sa.Column('run_repetidas', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('accounts_to_repeat', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('repetitions_count', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('repetidas_interval_seconds', sa.Integer(), nullable=False, server_default='7200'),
        sa.Column('partitions_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )
    print("[OK] Tabla bot_logueador_config creada")


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'bot_logueador_config' not in tables:
        print("[INFO] Tabla bot_logueador_config no existe, omitiendo rollback")
        return
    op.drop_table('bot_logueador_config')
    print("[OK] Tabla bot_logueador_config eliminada")
