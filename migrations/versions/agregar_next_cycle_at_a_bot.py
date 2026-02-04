"""agregar next_cycle_at a bot

Revision ID: agregar_next_cycle_at
Revises: crear_tabla_bot
Create Date: 2025-01-21 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'agregar_next_cycle_at'
down_revision = 'crear_tabla_bot'
branch_labels = None
depends_on = None


def upgrade():
    # Verificar si la columna ya existe antes de agregarla
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('bot')]
    
    if 'next_cycle_at' not in columns:
        op.add_column('bot', sa.Column('next_cycle_at', sa.DateTime(), nullable=True))
        print("[OK] Columna next_cycle_at agregada a la tabla bot")
    else:
        print("[INFO] Columna next_cycle_at ya existe, omitiendo migracion")


def downgrade():
    # Verificar si la columna existe antes de eliminarla
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('bot')]
    
    if 'next_cycle_at' in columns:
        op.drop_column('bot', 'next_cycle_at')
        print("[OK] Columna next_cycle_at eliminada de la tabla bot")
    else:
        print("[INFO] Columna next_cycle_at no existe, omitiendo rollback")

