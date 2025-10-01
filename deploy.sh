#!/bin/bash

echo "🚀 Desplegando API Login..."

# Crear volumen si no existe
echo "📦 Creando volumen de datos..."
sudo docker volume create api-login-data 2>/dev/null || echo "Volumen ya existe"

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

# Aplicar migraciones
echo "🗄️  Aplicando migraciones..."
sudo docker exec api-login-container flask db upgrade

# Verificar estado
echo "✅ Verificando estado..."
sudo docker ps | grep api-login-container

echo "🎉 Despliegue completado!"
echo "🌐 API disponible en: http://localhost"
echo "📊 Para ver logs: sudo docker logs -f api-login-container"
