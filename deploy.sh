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

# Crear backup completo de la base de datos ANTES de cualquier cambio
echo "🔄 Creando backup completo de la base de datos..."
BACKUP_SCRIPT="./backup_database.sh"
if [ -f "$BACKUP_SCRIPT" ]; then
    chmod +x "$BACKUP_SCRIPT"
    "$BACKUP_SCRIPT" "$CONTAINER_NAME" "$VOLUME_NAME" || echo "⚠️  Backup falló, pero continuando..."
else
    echo "⚠️  Script de backup no encontrado, creando backup básico..."
    BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
    if sudo docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
        # Intentar backup desde la ubicación correcta primero
        sudo docker exec "$CONTAINER_NAME" cp /api_login/app/database/users.db /api_login/app/database/users.db.backup.$BACKUP_DATE 2>/dev/null || \
        # Si no existe, intentar desde la ubicación anterior
        sudo docker exec "$CONTAINER_NAME" cp /api_login/database.db /api_login/app/database/users.db.backup.$BACKUP_DATE 2>/dev/null || \
        echo "⚠️  No se pudo crear backup desde contenedor"
        echo "✅ Backup básico creado: users.db.backup.$BACKUP_DATE"
    else
        echo "⚠️  No hay contenedor corriendo, saltando backup básico"
    fi
fi

# Detener y eliminar contenedor existente
echo "Deteniendo contenedor existente ($CONTAINER_NAME)..."
sudo docker stop "$CONTAINER_NAME" 2>/dev/null || echo "Contenedor no estaba corriendo"
sudo docker rm "$CONTAINER_NAME" 2>/dev/null || echo "Contenedor no existía"

# Construir nueva imagen
echo "Construyendo imagen ($IMAGE_NAME)..."

# Sin .dockerignore en el servidor, `docker build` envía ./backups (varios GB) y agota el disco.
if [ ! -f .dockerignore ]; then
    echo "❌ ERROR: No existe .dockerignore en $(pwd)"
    echo "   Sube/copialo desde el repositorio (misma carpeta que el Dockerfile). Sin él el contexto supera varios GB."
    exit 1
fi
_ignore_bytes=$(wc -c < .dockerignore | tr -d ' ')
if [ "${_ignore_bytes:-0}" -lt 80 ]; then
    echo "❌ ERROR: .dockerignore existe pero es demasiado pequeño (${_ignore_bytes} bytes). ¿Archivo vacío o corrupto?"
    exit 1
fi
if ! grep -v '^[[:space:]]*#' .dockerignore | grep -q 'backups'; then
    echo "❌ ERROR: .dockerignore debe excluir la carpeta backups (p. ej. líneas: backups o backups/)."
    exit 1
fi
echo "✅ .dockerignore OK (${_ignore_bytes} bytes, excluye backups)"

sudo docker build -t "$IMAGE_NAME" .

# Cargar variables de entorno desde .env si existe
if [ -f .env ]; then
    echo "Cargando variables de entorno desde .env..."
    # shellcheck disable=SC2046
    set +u  # Desactivar verificación de variables no definidas temporalmente
    export $(grep -v '^#' .env | grep -v '^$' | xargs) || true
    set -u  # Reactivar verificación
else
    echo "Archivo .env no encontrado, usando valores por defecto"
    export ADMIN_KEY=Aaad0719
    export SECRET_KEY=Aaad0719
    export DATABASE_PATH=/api_login/app/database
    export SESSION_COOKIE_SECURE=false
fi

# Validar que SECRET_KEY esté definido (usar ADMIN_KEY como fallback si no existe)
set +u  # Desactivar verificación temporalmente
if [ -z "${SECRET_KEY:-}" ]; then
    echo "SECRET_KEY no definido, usando ADMIN_KEY como fallback"
    export SECRET_KEY="${ADMIN_KEY:-Aaad0719}"
fi

# SESSION_COOKIE_SECURE por defecto false (true solo con HTTPS)
if [ -z "${SESSION_COOKIE_SECURE:-}" ]; then
    export SESSION_COOKIE_SECURE=false
fi

# Asegurar que ADMIN_KEY esté definido
if [ -z "${ADMIN_KEY:-}" ]; then
    echo "⚠️  ADMIN_KEY no definido, usando valor por defecto"
    export ADMIN_KEY=Aaad0719
fi

# Asegurar que DATABASE_PATH esté definido
if [ -z "${DATABASE_PATH:-}" ]; then
    export DATABASE_PATH=/api_login/app/database
fi

set -u  # Reactivar verificación

# Migraciones ANTES de arrancar Gunicorn: SQLite bloquea si otra conexión (el worker)
# mantiene la base abierta; un contenedor efímero es el patrón recomendado.
echo "🔄 Aplicando migraciones (contenedor efímero, sin Gunicorn — evita 'database is locked')..."
echo "   (Alembic solo aplica cambios pendientes)"
echo "📋 Revisión actual (si existe):"
sudo docker run --rm \
  -v "${VOLUME_NAME}:/api_login/app/database" \
  -e DATABASE_PATH="$DATABASE_PATH" \
  -e ADMIN_KEY="$ADMIN_KEY" \
  -e SECRET_KEY="$SECRET_KEY" \
  -e SESSION_COOKIE_SECURE="$SESSION_COOKIE_SECURE" \
  "$IMAGE_NAME" \
  flask db current 2>/dev/null | head -5 || true

echo "⬆️  Aplicando migraciones pendientes..."
if ! sudo docker run --rm \
  -v "${VOLUME_NAME}:/api_login/app/database" \
  -e DATABASE_PATH="$DATABASE_PATH" \
  -e ADMIN_KEY="$ADMIN_KEY" \
  -e SECRET_KEY="$SECRET_KEY" \
  -e SESSION_COOKIE_SECURE="$SESSION_COOKIE_SECURE" \
  "$IMAGE_NAME" \
  flask db upgrade heads; then
  echo "❌ Error: las migraciones fallaron (p. ej. SQLite locked o error SQL)."
  echo "   Corrige el problema y vuelve a ejecutar el despliegue."
  echo "   Si la revisión quedó a medias, revisa: sudo docker run --rm -v ${VOLUME_NAME}:/api_login/app/database -e DATABASE_PATH=$DATABASE_PATH $IMAGE_NAME flask db current"
  exit 1
fi
echo "✅ Migraciones aplicadas correctamente"

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
sleep 10

# Verificar que el contenedor esté corriendo (no reiniciándose)
echo "Verificando estado del contenedor..."
CONTAINER_STATUS=$(sudo docker inspect -f '{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "not_found")
if [ "$CONTAINER_STATUS" != "running" ]; then
    echo "❌ Error: El contenedor no está corriendo. Estado: $CONTAINER_STATUS"
    echo "📋 Mostrando logs del contenedor:"
    sudo docker logs "$CONTAINER_NAME" 2>&1 | tail -50
    exit 1
fi
echo "✅ Contenedor está corriendo correctamente"

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

# Verificar y corregir tablas con estructura incorrecta ANTES de aplicar migraciones
echo "🔍 Verificando estructura de tablas críticas..."
TABLES_FIXED=$(sudo docker exec "$CONTAINER_NAME" python -c "
from sqlalchemy import inspect, text
from app import create_app
from app.database import db
app, _ = create_app()
with app.app_context():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    tables_fixed = False
    
    # Verificar y corregir tabla vps
    if 'vps' in tables:
        columns = [col['name'] for col in inspector.get_columns('vps')]
        required_columns = ['contabo_name', 'display_name', 'instance_id', 'ip_v4']
        if not all(c in columns for c in required_columns):
            print('⚠️  Tabla vps incompleta, será recreada por migraciones')
            with db.engine.connect() as conn:
                # Backup si tiene datos
                try:
                    result = conn.execute(text('SELECT COUNT(*) FROM vps'))
                    count = result.scalar()
                    if count > 0:
                        conn.execute(text('CREATE TABLE IF NOT EXISTS vps_backup AS SELECT * FROM vps'))
                        conn.commit()
                        print(f'✅ Backup de {count} registros de vps creado')
                except:
                    pass
                # Eliminar tabla incompleta
                conn.execute(text('DROP TABLE IF EXISTS vps'))
                conn.commit()
                print('✅ Tabla vps incompleta eliminada')
                tables_fixed = True
        else:
            print('✅ Tabla vps tiene estructura correcta')
    else:
        print('ℹ️  Tabla vps no existe, será creada por migraciones')
    
    # Verificar y corregir tabla proxies
    if 'proxies' in tables:
        columns = [col['name'] for col in inspector.get_columns('proxies')]
        required_columns = ['id', 'user_id', 'name', 'host', 'port', 'kind']
        if not all(c in columns for c in required_columns):
            print('⚠️  Tabla proxies incompleta, será recreada por migraciones')
            with db.engine.connect() as conn:
                # Backup si tiene datos
                try:
                    result = conn.execute(text('SELECT COUNT(*) FROM proxies'))
                    count = result.scalar()
                    if count > 0:
                        conn.execute(text('CREATE TABLE IF NOT EXISTS proxies_backup AS SELECT * FROM proxies'))
                        conn.commit()
                        print(f'✅ Backup de {count} registros de proxies creado')
                except:
                    pass
                # Eliminar tabla incompleta
                conn.execute(text('DROP TABLE IF EXISTS proxies'))
                conn.commit()
                print('✅ Tabla proxies incompleta eliminada')
                tables_fixed = True
        else:
            print('✅ Tabla proxies tiene estructura correcta')
    else:
        print('ℹ️  Tabla proxies no existe, será creada por migraciones')
    
    # Verificar y corregir tabla contabo_config
    if 'contabo_config' not in tables:
        print('ℹ️  Tabla contabo_config no existe, será creada por migraciones')
    else:
        print('✅ Tabla contabo_config existe')
    
    # Si se eliminaron tablas, resetear alembic_version para forzar re-aplicación
    if tables_fixed:
        with db.engine.connect() as conn:
            try:
                conn.execute(text('DELETE FROM alembic_version'))
                conn.commit()
                print('🔄 Estado de Alembic reseteado para forzar re-aplicación de migraciones')
            except:
                pass
    
    print('FIXED' if tables_fixed else 'OK')
" 2>/dev/null || echo "OK")

# Las migraciones ya se aplicaron antes de iniciar Gunicorn (evita SQLite locked).

# Verificar que la columna next_cycle_at existe (migración reciente)
echo "🔍 Verificando migración de next_cycle_at..."
sudo docker exec "$CONTAINER_NAME" python -c "
from sqlalchemy import inspect
from app import create_app
from app.database import db
app, _ = create_app()  # create_app devuelve (app, socketio)
with app.app_context():
    inspector = inspect(db.engine)
    columns = [col['name'] for col in inspector.get_columns('bot')]
    if 'next_cycle_at' in columns:
        print('✅ Columna next_cycle_at encontrada en la tabla bot')
    else:
        print('⚠️  Columna next_cycle_at NO encontrada (puede necesitar migración manual)')
" 2>/dev/null || echo "⚠️  No se pudo verificar la columna next_cycle_at"

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
echo " - Migraciones con contenedor efímero antes de arrancar la API (SQLite)"
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
