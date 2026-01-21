#!/bin/bash

echo "🚀 Desplegando API Login..."

# Crear volumen si no existe
echo "📦 Creando volumen de datos..."
sudo docker volume create api-login-data 2>/dev/null || echo "Volumen ya existe"

# Crear backup de la base de datos si existe
echo "💾 Creando backup de la base de datos..."
if sudo docker ps -q -f name=api-login-container | grep -q .; then
    BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
    # Intentar backup desde la ubicación correcta primero
    sudo docker exec api-login-container cp /api_login/app/database/users.db /api_login/app/database/users.db.backup.$BACKUP_DATE 2>/dev/null || \
    # Si no existe, intentar desde la ubicación anterior
    sudo docker exec api-login-container cp /api_login/database.db /api_login/app/database/users.db.backup.$BACKUP_DATE 2>/dev/null || \
    echo "No se pudo crear backup"
    echo "📁 Backup creado: users.db.backup.$BACKUP_DATE"
else
    echo "ℹ️  No hay contenedor corriendo, saltando backup"
fi

# Detener y eliminar contenedor existente
echo "🛑 Deteniendo contenedor existente..."
sudo docker stop api-login-container 2>/dev/null || echo "Contenedor no estaba corriendo"
sudo docker rm api-login-container 2>/dev/null || echo "Contenedor no existía"

# Construir nueva imagen
echo "🔨 Construyendo imagen..."
sudo docker build -t api-login .

# Cargar variables de entorno desde .env si existe
if [ -f .env ]; then
    echo "📋 Cargando variables de entorno desde .env..."
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "⚠️  Archivo .env no encontrado, usando valores por defecto"
    export ADMIN_KEY=my_very_secret_key
    export SECRET_KEY=my_very_secret_key
    export DATABASE_PATH=/api_login/app/database
    export SESSION_COOKIE_SECURE=false
fi

# Validar que SECRET_KEY esté definido (usar ADMIN_KEY como fallback si no existe)
if [ -z "$SECRET_KEY" ]; then
    echo "⚠️  SECRET_KEY no definido, usando ADMIN_KEY como fallback"
    export SECRET_KEY="$ADMIN_KEY"
fi

# SESSION_COOKIE_SECURE por defecto false (true solo con HTTPS)
if [ -z "$SESSION_COOKIE_SECURE" ]; then
    export SESSION_COOKIE_SECURE=false
fi

# Ejecutar contenedor con volumen
echo "▶️  Ejecutando contenedor..."
sudo docker run -d \
  -p 80:80 \
  -v api-login-data:/api_login/app/database \
  -e DATABASE_PATH="$DATABASE_PATH" \
  -e ADMIN_KEY="$ADMIN_KEY" \
  -e SECRET_KEY="$SECRET_KEY" \
  -e SESSION_COOKIE_SECURE="$SESSION_COOKIE_SECURE" \
  --name api-login-container \
  --restart unless-stopped \
  api-login

# Esperar a que el contenedor esté listo
echo "⏳ Esperando a que el contenedor esté listo..."
sleep 5

# Verificar si las tablas ya existen antes de aplicar migraciones
echo "🔍 Verificando estado de la base de datos..."
TABLES_EXIST=$(sudo docker exec api-login-container python -c "
from app import create_app
from app.database import db
app = create_app()
with app.app_context():
    try:
        result = db.engine.execute('SELECT name FROM sqlite_master WHERE type=\"table\" AND name=\"user\"')
        if result.fetchone():
            print('EXISTS')
        else:
            print('NOT_EXISTS')
    except Exception as e:
        print('ERROR')
" 2>/dev/null)

if [ "$TABLES_EXIST" = "EXISTS" ]; then
    echo "✅ Las tablas ya existen, saltando migraciones para preservar datos"
else
    echo "🗄️  Aplicando migraciones (primera vez)..."
    sudo docker exec api-login-container flask db upgrade
    
    # Mover base de datos existente al volumen si existe en ubicación anterior
    echo "🔄 Verificando si hay base de datos en ubicación anterior..."
    if sudo docker exec api-login-container test -f /api_login/database.db; then
        echo "📦 Moviendo base de datos al volumen..."
        sudo docker exec api-login-container cp /api_login/database.db /api_login/app/database/users.db
        echo "✅ Base de datos movida al volumen"
    fi
fi

# Verificar estado
echo "✅ Verificando estado..."
sudo docker ps | grep api-login-container

echo "🎉 Despliegue completado!"
echo "🌐 API disponible en: http://localhost"
echo "📊 Para ver logs: sudo docker logs -f api-login-container"
echo ""
echo "🔒 Protecciones activadas:"
echo "   ✅ Backup automático antes del despliegue"
echo "   ✅ Verificación de tablas existentes"
echo "   ✅ Migraciones solo en primera instalación"
echo "   ✅ Volumen persistente para datos"
echo "   ✅ Sesiones seguras configuradas (SECRET_KEY)"
echo ""
echo "📝 Variables de entorno configuradas:"
echo "   - ADMIN_KEY: ${ADMIN_KEY:0:10}..."
echo "   - SECRET_KEY: ${SECRET_KEY:0:10}..."
echo "   - DATABASE_PATH: $DATABASE_PATH"
echo "   - SESSION_COOKIE_SECURE: $SESSION_COOKIE_SECURE"
