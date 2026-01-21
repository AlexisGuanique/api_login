#!/bin/bash

# Script para aplicar la migración de next_cycle_at manualmente
# Uso: ./apply_migration.sh

CONTAINER_NAME="${CONTAINER_NAME:-api-login-test-container}"

echo "Aplicando migración para agregar next_cycle_at a la tabla bot..."

# Verificar que el contenedor esté corriendo
if ! sudo docker ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ Error: El contenedor $CONTAINER_NAME no está corriendo"
    exit 1
fi

echo "Verificando estado actual de migraciones..."
sudo docker exec "$CONTAINER_NAME" flask db current

echo "Aplicando migraciones pendientes..."
sudo docker exec "$CONTAINER_NAME" flask db upgrade heads

if [ $? -eq 0 ]; then
    echo "✅ Migraciones aplicadas exitosamente"
    
    # Verificar que la columna se agregó correctamente
    echo "Verificando que la columna next_cycle_at existe..."
    sudo docker exec "$CONTAINER_NAME" python -c "
from sqlalchemy import text, inspect
from app import create_app
from app.database import db
app = create_app()
with app.app_context():
    inspector = inspect(db.engine)
    columns = [col['name'] for col in inspector.get_columns('bot')]
    if 'next_cycle_at' in columns:
        print('✅ Columna next_cycle_at existe en la tabla bot')
    else:
        print('❌ Columna next_cycle_at NO existe en la tabla bot')
"
else
    echo "❌ Error al aplicar migraciones"
    exit 1
fi

