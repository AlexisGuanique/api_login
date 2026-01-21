#!/bin/bash

# Script para verificar el estado de la base de datos
# Uso: ./verify_database.sh [CONTAINER_NAME]

set -euo pipefail

CONTAINER_NAME="${1:-api-login-container}"

echo "🔍 Verificando estado de la base de datos en $CONTAINER_NAME..."

# Verificar que el contenedor está corriendo
if ! sudo docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
    echo "❌ Error: El contenedor $CONTAINER_NAME no está corriendo"
    exit 1
fi

echo ""
echo "📋 Paso 1: Verificando tablas existentes..."
sudo docker exec "$CONTAINER_NAME" python -c "
from sqlalchemy import create_engine, text, inspect
import os
database_path = os.environ.get('DATABASE_PATH', '/api_login/app/database')
db_path = f'{database_path}/users.db'
engine = create_engine(f'sqlite:///{db_path}')
inspector = inspect(engine)
tables = inspector.get_table_names()
print('Tablas existentes:')
for table in tables:
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
echo "📋 Paso 2: Verificando estado de migraciones..."
sudo docker exec "$CONTAINER_NAME" flask db current 2>/dev/null || echo "   No hay migraciones aplicadas"

echo ""
echo "📋 Paso 3: Verificando revisiones disponibles..."
sudo docker exec "$CONTAINER_NAME" flask db heads 2>/dev/null || echo "   No se pudieron obtener revisiones"

echo ""
echo "✅ Verificación completada"

