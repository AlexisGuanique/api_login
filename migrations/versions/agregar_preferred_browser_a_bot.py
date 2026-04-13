"""agregar preferred_browser a bot

Revision ID: agregar_preferred_browser
Revises: 918abd894d94
Create Date: 2026-04-13 10:15:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'agregar_preferred_browser'
down_revision = '918abd894d94'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('bot')]

    if 'preferred_browser' not in columns:
        op.add_column('bot', sa.Column('preferred_browser', sa.String(length=100), nullable=True))
        print("[OK] Columna preferred_browser agregada a la tabla bot")
    else:
        print("[INFO] Columna preferred_browser ya existe, omitiendo migracion")


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('bot')]

    if 'preferred_browser' in columns:
        op.drop_column('bot', 'preferred_browser')
        print("[OK] Columna preferred_browser eliminada de la tabla bot")
    else:
        print("[INFO] Columna preferred_browser no existe, omitiendo rollback")
