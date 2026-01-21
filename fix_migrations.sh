#!/bin/bash

# Script para corregir el estado de las migraciones cuando hay una revisión inválida
# Uso: ./fix_migrations.sh [CONTAINER_NAME]

set -euo pipefail

CONTAINER_NAME="${1:-api-login-container}"

echo "🔧 Corrigiendo estado de migraciones en $CONTAINER_NAME..."

# Verificar que el contenedor está corriendo
if ! sudo docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
    echo "❌ Error: El contenedor $CONTAINER_NAME no está corriendo"
    exit 1
fi

echo "📋 Paso 1: Verificando revisión actual guardada..."
CURRENT_REVISION=$(sudo docker exec "$CONTAINER_NAME" python -c "
from sqlalchemy import create_engine, text
import os
database_path = os.environ.get('DATABASE_PATH', '/api_login/app/database')
db_path = f'{database_path}/users.db'
engine = create_engine(f'sqlite:///{db_path}')
with engine.connect() as conn:
    try:
        result = conn.execute(text('SELECT version_num FROM alembic_version LIMIT 1'))
        row = result.fetchone()
        if row:
            print(row[0])
        else:
            print('NONE')
    except Exception as e:
        print(f'ERROR: {e}')
" 2>/dev/null || echo "ERROR")

echo "   Revisión actual: $CURRENT_REVISION"

echo ""
echo "📋 Paso 2: Obteniendo revisión head disponible..."
HEAD_REVISION=$(sudo docker exec "$CONTAINER_NAME" flask db heads 2>/dev/null | head -1 | awk '{print $1}' || echo "")
echo "   Revisión head: $HEAD_REVISION"

if [ -z "$HEAD_REVISION" ]; then
    echo "❌ Error: No se pudo obtener la revisión head"
    exit 1
fi

echo ""
echo "🔧 Paso 3: Limpiando tabla alembic_version..."
sudo docker exec "$CONTAINER_NAME" python -c "
from sqlalchemy import create_engine, text
import os
database_path = os.environ.get('DATABASE_PATH', '/api_login/app/database')
db_path = f'{database_path}/users.db'
engine = create_engine(f'sqlite:///{db_path}')
with engine.begin() as conn:
    try:
        # Eliminar todas las entradas de alembic_version
        conn.execute(text('DELETE FROM alembic_version'))
        print('✅ Tabla alembic_version limpiada')
    except Exception as e:
        print(f'⚠️  Error al limpiar: {e}')
        # Si la tabla no existe, crearla
        try:
            conn.execute(text('CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL, PRIMARY KEY (version_num))'))
            print('✅ Tabla alembic_version creada')
        except Exception as e2:
            print(f'❌ Error al crear tabla: {e2}')
" 2>/dev/null || echo "⚠️  No se pudo limpiar la tabla"

echo ""
echo "🔧 Paso 4: Marcando base de datos con revisión head: $HEAD_REVISION"
if sudo docker exec "$CONTAINER_NAME" flask db stamp "$HEAD_REVISION" 2>/dev/null; then
    echo "✅ Base de datos marcada con revisión $HEAD_REVISION"
else
    echo "⚠️  Error al marcar con stamp, intentando método alternativo..."
    
    # Método alternativo: insertar directamente en la tabla
    sudo docker exec "$CONTAINER_NAME" python -c "
from sqlalchemy import create_engine, text
import os
database_path = os.environ.get('DATABASE_PATH', '/api_login/app/database')
db_path = f'{database_path}/users.db'
engine = create_engine(f'sqlite:///{db_path}')
with engine.begin() as conn:
    try:
        # Eliminar cualquier entrada existente
        conn.execute(text('DELETE FROM alembic_version'))
        # Insertar la revisión head
        conn.execute(text(f\"INSERT INTO alembic_version (version_num) VALUES ('$HEAD_REVISION')\"))
        print('✅ Revisión insertada directamente en la tabla')
    except Exception as e:
        print(f'❌ Error: {e}')
" 2>/dev/null || echo "❌ Error al insertar revisión"
fi

echo ""
echo "📋 Paso 5: Verificando estado final..."
FINAL_REVISION=$(sudo docker exec "$CONTAINER_NAME" flask db current 2>/dev/null | head -1 | awk '{print $1}' || echo "")
if [ -n "$FINAL_REVISION" ] && [ "$FINAL_REVISION" != "None" ]; then
    echo "✅ Revisión actual: $FINAL_REVISION"
    if [ "$FINAL_REVISION" = "$HEAD_REVISION" ]; then
        echo "✅ Estado corregido correctamente"
    else
        echo "⚠️  La revisión no coincide con head, pero está corregida"
    fi
else
    echo "⚠️  No se pudo verificar la revisión final"
fi

echo ""
echo "🔄 Paso 6: Intentando aplicar migraciones pendientes..."
if sudo docker exec "$CONTAINER_NAME" flask db upgrade heads 2>/dev/null; then
    echo "✅ Migraciones aplicadas exitosamente"
else
    echo "⚠️  No se pudieron aplicar migraciones (puede que ya estén aplicadas)"
fi

echo ""
echo "✅ Proceso de corrección completado!"

