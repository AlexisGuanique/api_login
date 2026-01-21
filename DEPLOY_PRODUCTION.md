# 🚀 Guía de Despliegue a Producción

Esta guía te ayudará a desplegar la API Login a producción **sin perder datos**.

## 📋 Pre-requisitos

1. Acceso SSH al servidor de producción
2. Docker instalado en el servidor
3. Acceso sudo en el servidor
4. **Backup completo de la base de datos actual** (recomendado)

## 🔄 Proceso de Despliegue Seguro

### Paso 1: Backup Completo (OBLIGATORIO)

**ANTES de hacer cualquier cambio**, crea un backup completo:

```bash
# Opción 1: Usar el script de backup automático
cd /ruta/a/api_login
./backup_database.sh

# Opción 2: Backup manual del volumen
sudo docker run --rm \
  -v api-login-data:/data \
  -v $(pwd)/backups:/backup \
  alpine:latest \
  tar czf /backup/volume-backup-$(date +%Y%m%d_%H%M%S).tar.gz -C /data .
```

### Paso 2: Verificar Estado Actual

```bash
# Verificar contenedor actual
sudo docker ps -a | grep api-login

# Verificar volumen
sudo docker volume ls | grep api-login

# Verificar datos en el volumen
sudo docker run --rm -v api-login-data:/data alpine:latest ls -la /data/
```

### Paso 3: Subir Código al Servidor

```bash
# Desde tu máquina local
rsync -avz --exclude 'venv' --exclude '__pycache__' --exclude '*.pyc' \
  ./api_login/ usuario@servidor:/ruta/a/api_login/

# O usar git
git pull origin main  # en el servidor
```

### Paso 4: Desplegar

```bash
cd /ruta/a/api_login

# Verificar que el script de backup existe
chmod +x backup_database.sh deploy.sh

# Desplegar (el script hará backup automáticamente)
./deploy.sh
```

**O con variables personalizadas:**

```bash
APP_PORT=80 \
CONTAINER_NAME=api-login-container \
VOLUME_NAME=api-login-data \
IMAGE_NAME=api-login \
./deploy.sh
```

### Paso 5: Verificar Despliegue

```bash
# Verificar que el contenedor está corriendo
sudo docker ps | grep api-login-container

# Verificar logs
sudo docker logs -f api-login-container

# Verificar que los datos están intactos
sudo docker exec api-login-container python -c "
from app import create_app
from app.models.user import User
app = create_app()
with app.app_context():
    users = User.query.count()
    print(f'✅ Usuarios en la base de datos: {users}')
"
```

## 🔒 Protecciones Incluidas

El script de deploy incluye las siguientes protecciones:

1. ✅ **Backup automático** antes de cualquier cambio
2. ✅ **Volumen persistente** - Los datos se guardan en un volumen Docker que persiste entre despliegues
3. ✅ **Migraciones seguras** - Alembic solo aplica cambios pendientes
4. ✅ **Verificación de estado** - Verifica que el contenedor esté corriendo correctamente
5. ✅ **Rollback fácil** - Si algo falla, puedes restaurar desde el backup

## 🔄 Restaurar desde Backup

Si necesitas restaurar desde un backup:

```bash
# 1. Detener el contenedor
sudo docker stop api-login-container

# 2. Restaurar desde backup del volumen
sudo docker run --rm \
  -v api-login-data:/data \
  -v $(pwd)/backups:/backup \
  alpine:latest \
  tar xzf /backup/volume-backup-YYYYMMDD_HHMMSS.tar.gz -C /data

# 3. Reiniciar el contenedor
sudo docker start api-login-container
```

## ⚠️ Variables de Entorno Importantes

Asegúrate de tener un archivo `.env` con:

```bash
ADMIN_KEY=tu_clave_secreta_muy_segura
SECRET_KEY=tu_clave_secreta_muy_segura
DATABASE_PATH=/api_login/app/database
SESSION_COOKIE_SECURE=false  # true solo si usas HTTPS
```

## 📊 Verificación Post-Despliegue

Después del despliegue, verifica:

1. ✅ Contenedor corriendo: `sudo docker ps | grep api-login`
2. ✅ API respondiendo: `curl http://localhost/api/health` (si existe)
3. ✅ Usuarios intactos: Verificar que el número de usuarios es correcto
4. ✅ Migraciones aplicadas: `sudo docker exec api-login-container flask db current`
5. ✅ WebSocket funcionando: Probar conexión desde un bot

## 🆘 Solución de Problemas

### Error: "unable to open database file"

```bash
# Verificar permisos del volumen
sudo docker exec api-login-container ls -la /api_login/app/database/

# Crear directorio si no existe
sudo docker exec api-login-container mkdir -p /api_login/app/database
sudo docker exec api-login-container chmod 755 /api_login/app/database
```

### Error: "Migration failed"

```bash
# Ver estado de migraciones
sudo docker exec api-login-container flask db current

# Ver historial de migraciones
sudo docker exec api-login-container flask db history

# Si es necesario, marcar migración como aplicada manualmente
sudo docker exec api-login-container flask db stamp head
```

### Contenedor se reinicia constantemente

```bash
# Ver logs para identificar el error
sudo docker logs api-login-container

# Verificar variables de entorno
sudo docker exec api-login-container env | grep -E 'ADMIN_KEY|SECRET_KEY|DATABASE'
```

## 📝 Notas Importantes

- **NUNCA elimines el volumen** `api-login-data` sin hacer backup primero
- **Siempre haz backup** antes de desplegar cambios importantes
- **Verifica las migraciones** después de cada despliegue
- **Mantén los backups** por al menos 30 días

