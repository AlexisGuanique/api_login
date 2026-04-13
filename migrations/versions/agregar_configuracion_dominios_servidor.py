"""agregar configuracion dominios servidor

Revision ID: agregar_config_dominios_servidor
Revises: agregar_bot_browser_user_agent
Create Date: 2026-04-13 16:05:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'agregar_config_dominios_servidor'
down_revision = 'agregar_bot_browser_user_agent'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'bot_domain_global_config' not in existing_tables:
        op.create_table(
            'bot_domain_global_config',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('is33mail', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('random_domains', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('fill_domain', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('domain', sa.String(length=255), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id')
        )

    if 'bot_domain_entry' not in existing_tables:
        op.create_table(
            'bot_domain_entry',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('domain', sa.String(length=255), nullable=False),
            sa.Column('fill_domain', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'domain', name='uq_user_domain_entry')
        )
        op.create_index('idx_bot_domain_entry_user_id', 'bot_domain_entry', ['user_id'], unique=False)

    if 'bot_random_tld_entry' not in existing_tables:
        op.create_table(
            'bot_random_tld_entry',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('tld', sa.String(length=64), nullable=False),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'tld', name='uq_user_random_tld_entry')
        )
        op.create_index('idx_bot_random_tld_entry_user_id', 'bot_random_tld_entry', ['user_id'], unique=False)


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'bot_random_tld_entry' in existing_tables:
        op.drop_index('idx_bot_random_tld_entry_user_id', table_name='bot_random_tld_entry')
        op.drop_table('bot_random_tld_entry')

    if 'bot_domain_entry' in existing_tables:
        op.drop_index('idx_bot_domain_entry_user_id', table_name='bot_domain_entry')
        op.drop_table('bot_domain_entry')

    if 'bot_domain_global_config' in existing_tables:
        op.drop_table('bot_domain_global_config')
