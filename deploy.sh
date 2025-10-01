#!/bin/bash

echo "🚀 Desplegando API Login..."

# Crear volumen si no existe
echo "📦 Creando volumen de datos..."
sudo docker volume create api-login-data 2>/dev/null || echo "Volumen ya existe"

# Crear backup de la base de datos si existe
echo "💾 Creando backup de la base de datos..."
if sudo docker ps -q -f name=api-login-container | grep -q .; then
    BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
    sudo docker exec api-login-container cp /api_login/app/database/users.db /api_login/app/database/users.db.backup.$BACKUP_DATE 2>/dev/null || echo "No se pudo crear backup"
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

# Ejecutar contenedor con volumen
echo "▶️  Ejecutando contenedor..."
sudo docker run -d \
  -p 80:80 \
  -v api-login-data:/api_login/app/database \
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
