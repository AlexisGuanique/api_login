#!/bin/bash

set -euo pipefail

echo "Desplegando API Login..."

# Permite desplegar TEST/PROD en paralelo sin pisarse.
# Puedes sobreescribir estas variables al ejecutar:
# APP_PORT=8081 CONTAINER_NAME=api-login-test VOLUME_NAME=api-login-test-data IMAGE_NAME=api-login-test ./deploy.sh
APP_PORT="${APP_PORT:-80}"                 # puerto host
CONTAINER_PORT="${CONTAINER_PORT:-80}"     # puerto dentro del contenedor (Gunicorn escucha aquí)
CONTAINER_NAME="${CONTAINER_NAME:-api-login-container}"
VOLUME_NAME="${VOLUME_NAME:-api-login-data}"
IMAGE_NAME="${IMAGE_NAME:-api-login}"

# Crear volumen si no existe
echo "Creando volumen de datos ($VOLUME_NAME)..."
sudo docker volume create "$VOLUME_NAME" 2>/dev/null || echo "Volumen ya existe"

# Crear backup de la base de datos si existe
echo "Creando backup de la base de datos..."
if sudo docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
    BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
    # Intentar backup desde la ubicación correcta primero
    sudo docker exec "$CONTAINER_NAME" cp /api_login/app/database/users.db /api_login/app/database/users.db.backup.$BACKUP_DATE 2>/dev/null || \
    # Si no existe, intentar desde la ubicación anterior
    sudo docker exec "$CONTAINER_NAME" cp /api_login/database.db /api_login/app/database/users.db.backup.$BACKUP_DATE 2>/dev/null || \
    echo "No se pudo crear backup"
    echo "Backup creado: users.db.backup.$BACKUP_DATE"
else
    echo "No hay contenedor corriendo, saltando backup"
fi

# Detener y eliminar contenedor existente
echo "Deteniendo contenedor existente ($CONTAINER_NAME)..."
sudo docker stop "$CONTAINER_NAME" 2>/dev/null || echo "Contenedor no estaba corriendo"
sudo docker rm "$CONTAINER_NAME" 2>/dev/null || echo "Contenedor no existía"

# Construir nueva imagen
echo "Construyendo imagen ($IMAGE_NAME)..."
sudo docker build -t "$IMAGE_NAME" .

# Cargar variables de entorno desde .env si existe
if [ -f .env ]; then
    echo "Cargando variables de entorno desde .env..."
    # shellcheck disable=SC2046
    export $(grep -v '^#' .env | xargs) || true
else
    echo "Archivo .env no encontrado, usando valores por defecto"
    export ADMIN_KEY=my_very_secret_key
    export SECRET_KEY=my_very_secret_key
    export DATABASE_PATH=/api_login/app/database
    export SESSION_COOKIE_SECURE=false
fi

# Validar que SECRET_KEY esté definido (usar ADMIN_KEY como fallback si no existe)
if [ -z "$SECRET_KEY" ]; then
    echo "SECRET_KEY no definido, usando ADMIN_KEY como fallback"
    export SECRET_KEY="$ADMIN_KEY"
fi

# SESSION_COOKIE_SECURE por defecto false (true solo con HTTPS)
if [ -z "$SESSION_COOKIE_SECURE" ]; then
    export SESSION_COOKIE_SECURE=false
fi

# Ejecutar contenedor con volumen
echo "Ejecutando contenedor ($CONTAINER_NAME) en puerto host $APP_PORT..."
sudo docker run -d \
  -p "${APP_PORT}:${CONTAINER_PORT}" \
  -v "${VOLUME_NAME}:/api_login/app/database" \
  -e DATABASE_PATH="$DATABASE_PATH" \
  -e ADMIN_KEY="$ADMIN_KEY" \
  -e SECRET_KEY="$SECRET_KEY" \
  -e SESSION_COOKIE_SECURE="$SESSION_COOKIE_SECURE" \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  "$IMAGE_NAME"

# Esperar a que el contenedor esté listo
echo "Esperando a que el contenedor esté listo..."
sleep 5

# Verificar si las tablas ya existen antes de aplicar migraciones
echo "Verificando estado de la base de datos..."
TABLES_EXIST=$(sudo docker exec "$CONTAINER_NAME" python -c "
from sqlalchemy import text
from app import create_app
from app.database import db
app = create_app()
with app.app_context():
    try:
        with db.engine.connect() as conn:
            result = conn.execute(text('SELECT name FROM sqlite_master WHERE type=\"table\" AND name=\"user\"'))
            print('EXISTS' if result.fetchone() else 'NOT_EXISTS')
    except Exception:
        print('ERROR')
" 2>/dev/null || true)

if [ "$TABLES_EXIST" = "EXISTS" ]; then
    echo "Las tablas ya existen, saltando migraciones para preservar datos"
else
    echo "Aplicando migraciones (primera vez)..."
    sudo docker exec "$CONTAINER_NAME" flask db upgrade
    
    # Mover base de datos existente al volumen si existe en ubicación anterior
    echo "Verificando si hay base de datos en ubicación anterior..."
    if sudo docker exec "$CONTAINER_NAME" test -f /api_login/database.db; then
        echo "Moviendo base de datos al volumen..."
        sudo docker exec "$CONTAINER_NAME" cp /api_login/database.db /api_login/app/database/users.db
        echo "Base de datos movida al volumen"
    fi
fi

# Verificar estado
echo "Verificando estado..."
sudo docker ps | grep "$CONTAINER_NAME"

echo "Despliegue completado!"
echo "API disponible en: http://localhost:${APP_PORT}"
echo "Para ver logs: sudo docker logs -f ${CONTAINER_NAME}"
echo ""
echo "Protecciones activadas:"
echo " - Backup automático antes del despliegue"
echo " - Verificación de tablas existentes"
echo " - Migraciones solo en primera instalación"
echo " - Volumen persistente para datos"
echo " - Sesiones seguras configuradas (SECRET_KEY)"
echo ""
echo "Variables de entorno:"
echo " - APP_PORT: $APP_PORT"
echo " - CONTAINER_NAME: $CONTAINER_NAME"
echo " - VOLUME_NAME: $VOLUME_NAME"
echo " - IMAGE_NAME: $IMAGE_NAME"
echo " - ADMIN_KEY: ${ADMIN_KEY:0:10}..."
echo " - SECRET_KEY: ${SECRET_KEY:0:10}..."
echo " - DATABASE_PATH: $DATABASE_PATH"
echo " - SESSION_COOKIE_SECURE: $SESSION_COOKIE_SECURE"
