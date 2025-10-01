# API de Autenticación con Flask

Esta aplicación proporciona una API RESTful construida con Flask para la gestión de usuarios, autenticación y verificación de tokens.

## 🚀 Despliegue Rápido

### 1. Configuración Inicial

```bash
# Clonar el repositorio
git clone <tu-repositorio>
cd api_login

# Crear archivo de configuración
cat > .env << EOF
ADMIN_KEY=my_very_secret_key
DATABASE_PATH=/api_login/app/database
EOF

# Verificar configuración
cat .env
```

### 2. Desplegar con Docker

```bash
# Ejecutar script de despliegue
./deploy.sh
```

### 3. Verificar Despliegue

```bash
# Verificar que el contenedor está corriendo
sudo docker ps | grep api-login-container

# Probar la API
curl -X GET http://localhost/api/auth/users -H "Admin-Key: my_very_secret_key"
```

## 📋 Configuración de Variables de Entorno

### Opción 1: Archivo .env (Recomendado)

```bash
# Crear archivo .env
cat > .env << EOF
ADMIN_KEY=tu_clave_secreta_aqui
DATABASE_PATH=/api_login/app/database
EOF
```

### Opción 2: Variables de Entorno del Sistema

```bash
# Exportar variables
export ADMIN_KEY="tu_clave_secreta"
export DATABASE_PATH="/api_login/app/database"

# Luego ejecutar despliegue
./deploy.sh
```

### Opción 3: Docker Compose

```bash
# Las variables se cargan automáticamente desde .env
docker-compose up -d
```

## 🔧 Comandos Útiles

### Gestión del Contenedor

```bash
# Ver logs de la aplicación
sudo docker logs -f api-login-container

# Detener contenedor
sudo docker stop api-login-container

# Eliminar contenedor
sudo docker rm api-login-container

# Reiniciar contenedor
sudo docker restart api-login-container
```

### Gestión de la Base de Datos

```bash
# Verificar estado de la base de datos
sudo docker exec api-login-container ls -la /api_login/app/database/

# Crear directorio de base de datos manualmente (si es necesario)
sudo docker exec api-login-container mkdir -p /api_login/app/database
sudo docker exec api-login-container chmod 755 /api_login/app/database

# Ejecutar migraciones manualmente
sudo docker exec api-login-container flask db upgrade

# Crear base de datos manualmente (si es necesario)
sudo docker exec api-login-container python -c "
import sqlite3
import os
os.makedirs('/api_login/app/database', exist_ok=True)
conn = sqlite3.connect('/api_login/app/database/users.db')
conn.close()
print('Base de datos creada exitosamente')
"
```

### Gestión de Volúmenes

```bash
# Ver volúmenes Docker
sudo docker volume ls

# Inspeccionar volumen de datos
sudo docker volume inspect api-login-data

# Ver contenido del volumen
sudo ls -la /var/lib/docker/volumes/api-login-data/_data/

# Eliminar volumen (¡CUIDADO! Esto borra todos los datos)
sudo docker volume rm api-login-data
```

## 🐛 Solución de Problemas

### Error: "unable to open database file"

```bash
# 1. Verificar que el directorio existe
sudo docker exec api-login-container ls -la /api_login/app/database/

# 2. Crear directorio si no existe
sudo docker exec api-login-container mkdir -p /api_login/app/database

# 3. Verificar permisos
sudo docker exec api-login-container chmod 755 /api_login/app/database

# 4. Crear base de datos manualmente
sudo docker exec api-login-container python -c "
import sqlite3
import os
os.makedirs('/api_login/app/database', exist_ok=True)
conn = sqlite3.connect('/api_login/app/database/users.db')
conn.close()
print('Base de datos creada')
"

# 5. Ejecutar migraciones
sudo docker exec api-login-container flask db upgrade
```

### Error: "Acceso no autorizado"

```bash
# Verificar que ADMIN_KEY esté configurado correctamente
sudo docker exec api-login-container env | grep ADMIN_KEY

# Usar la clave correcta en las peticiones
curl -X GET http://localhost/api/auth/users -H "Admin-Key: my_very_secret_key"
```

### Error: Variables de entorno no se cargan

```bash
# Verificar archivo .env
cat .env

# Verificar variables en el contenedor
sudo docker exec api-login-container env | grep -E "(DATABASE_PATH|ADMIN_KEY)"

# Recrear contenedor con variables correctas
sudo docker stop api-login-container
sudo docker rm api-login-container
./deploy.sh
```

## 📊 Monitoreo

### Verificar Estado de la Aplicación

```bash
# Estado del contenedor
sudo docker ps | grep api-login-container

# Logs en tiempo real
sudo docker logs -f api-login-container

# Uso de recursos
sudo docker stats api-login-container
```

### Probar Endpoints

```bash
# Obtener todos los usuarios
curl -X GET http://localhost/api/auth/users -H "Admin-Key: my_very_secret_key"

# Crear usuario
curl -X POST http://localhost/api/auth/register \
  -H "Content-Type: application/json" \
  -H "Admin-Key: my_very_secret_key" \
  -d '{"username": "testuser", "password": "testpass123"}'

# Login
curl -X POST http://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpass123"}'
```

## 🔒 Seguridad

### Para Producción

```bash
# 1. Cambiar ADMIN_KEY por una clave segura
export ADMIN_KEY="clave_super_secreta_produccion_$(openssl rand -hex 32)"

# 2. Crear archivo .env.production
cat > .env.production << EOF
ADMIN_KEY=$ADMIN_KEY
DATABASE_PATH=/api_login/app/database
EOF

# 3. Usar archivo de producción
cp .env.production .env

# 4. Desplegar
./deploy.sh
```

### Backup de Base de Datos

```bash
# Crear backup manual
sudo docker exec api-login-container cp /api_login/app/database/users.db /api_login/app/database/users.db.backup.$(date +%Y%m%d_%H%M%S)

# Restaurar backup
sudo docker exec api-login-container cp /api_login/app/database/users.db.backup.20251001_185437 /api_login/app/database/users.db
```

## 📁 Estructura del Proyecto

```
api_login/
├── app/
│   ├── __init__.py          # Configuración de Flask
│   ├── config.py            # Configuración de la aplicación
│   ├── database.py          # Configuración de SQLAlchemy
│   ├── controllers/         # Controladores de la API
│   ├── models/              # Modelos de datos
│   └── utils/               # Utilidades
├── migrations/              # Migraciones de base de datos
├── deploy.sh               # Script de despliegue
├── docker-compose.yml      # Configuración de Docker Compose
├── Dockerfile              # Imagen de Docker
├── .env                    # Variables de entorno (crear manualmente)
├── env.example             # Ejemplo de variables de entorno
└── README.md               # Este archivo
```

## 🆘 Soporte

Si encuentras problemas:

1. Verifica que el archivo `.env` existe y tiene la configuración correcta
2. Revisa los logs del contenedor: `sudo docker logs api-login-container`
3. Verifica que el directorio de la base de datos existe y tiene permisos correctos
4. Asegúrate de que las variables de entorno se están cargando correctamente

Para más información sobre los endpoints de la API, consulta la documentación en el código fuente.