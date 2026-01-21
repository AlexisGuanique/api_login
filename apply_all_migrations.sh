#!/bin/bash

# Script para aplicar todas las migraciones desde el principio
# Uso: ./apply_all_migrations.sh [CONTAINER_NAME]

set -euo pipefail

CONTAINER_NAME="${1:-api-login-container}"

echo "🔄 Aplicando todas las migraciones desde el principio en $CONTAINER_NAME..."

# Verificar que el contenedor está corriendo
if ! sudo docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
    echo "❌ Error: El contenedor $CONTAINER_NAME no está corriendo"
    exit 1
fi

echo ""
echo "📋 Paso 1: Verificando tablas existentes..."
sudo docker exec "$CONTAINER_NAME" python -c "
from sqlalchemy import create_engine, inspect
import os
database_path = os.environ.get('DATABASE_PATH', '/api_login/app/database')
db_path = f'{database_path}/users.db'
engine = create_engine(f'sqlite:///{db_path}')
inspector = inspect(engine)
tables = inspector.get_table_names()
print('Tablas existentes:')
for table in sorted(tables):
    print(f'  - {table}')
" 2>/dev/null || echo "⚠️  Error al verificar tablas"

echo ""
echo "📋 Paso 2: Limpiando estado de migraciones..."
sudo docker exec "$CONTAINER_NAME" python -c "
from sqlalchemy import create_engine, text
import os
database_path = os.environ.get('DATABASE_PATH', '/api_login/app/database')
db_path = f'{database_path}/users.db'
engine = create_engine(f'sqlite:///{db_path}')
with engine.begin() as conn:
    try:
        conn.execute(text('DELETE FROM alembic_version'))
        print('✅ Tabla alembic_version limpiada')
    except Exception as e:
        print(f'⚠️  Error: {e}')
" 2>/dev/null || echo "⚠️  No se pudo limpiar"

echo ""
echo "📋 Paso 3: Aplicando todas las migraciones desde el principio..."
if sudo docker exec "$CONTAINER_NAME" flask db upgrade heads; then
    echo "✅ Migraciones aplicadas exitosamente"
else
    echo "❌ Error al aplicar migraciones"
    exit 1
fi

echo ""
echo "📋 Paso 4: Verificando tablas después de migraciones..."
sudo docker exec "$CONTAINER_NAME" python -c "
from sqlalchemy import create_engine, inspect
import os
database_path = os.environ.get('DATABASE_PATH', '/api_login/app/database')
db_path = f'{database_path}/users.db'
engine = create_engine(f'sqlite:///{db_path}')
inspector = inspect(engine)
tables = inspector.get_table_names()
print('Tablas existentes después de migraciones:')
for table in sorted(tables):
    print(f'  - {table}')
if 'bot' in tables:
    print('✅ Tabla bot existe')
    columns = [col['name'] for col in inspector.get_columns('bot')]
    print(f'   Columnas: {", ".join(columns)}')
    if 'next_cycle_at' in columns:
        print('✅ Columna next_cycle_at encontrada')
    else:
        print('❌ Columna next_cycle_at NO encontrada')
else:
    print('❌ Tabla bot NO existe')
" 2>/dev/null || echo "⚠️  Error al verificar tablas"

echo ""
echo "✅ Proceso completado!"

