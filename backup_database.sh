#!/bin/bash

# Script para hacer backup completo de la base de datos antes de desplegar
# Uso: ./backup_database.sh [CONTAINER_NAME] [VOLUME_NAME]

set -euo pipefail

CONTAINER_NAME="${1:-api-login-container}"
VOLUME_NAME="${2:-api-login-data}"
BACKUP_DIR="./backups"
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)

echo "🔄 Creando backup de la base de datos..."
echo "   Contenedor: $CONTAINER_NAME"
echo "   Volumen: $VOLUME_NAME"

# Crear directorio de backups si no existe
mkdir -p "$BACKUP_DIR"

# Método 1: Backup desde el contenedor si está corriendo
if sudo docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
    echo "📦 Método 1: Backup desde contenedor activo..."
    
    # Backup de la base de datos principal
    if sudo docker exec "$CONTAINER_NAME" test -f /api_login/app/database/users.db; then
        echo "   ✅ Copiando users.db desde contenedor..."
        sudo docker cp "$CONTAINER_NAME:/api_login/app/database/users.db" "$BACKUP_DIR/users.db.$BACKUP_DATE"
        echo "   ✅ Backup creado: $BACKUP_DIR/users.db.$BACKUP_DATE"
    fi
    
    # Backup de archivos adicionales en el directorio de base de datos
    echo "   📋 Copiando archivos adicionales..."
    sudo docker exec "$CONTAINER_NAME" find /api_login/app/database -type f -name "*.db*" -exec sh -c 'for f; do echo "$f"; done' _ {} \; | while read -r file; do
        if [ -n "$file" ]; then
            filename=$(basename "$file")
            echo "      Copiando $filename..."
            sudo docker cp "$CONTAINER_NAME:$file" "$BACKUP_DIR/$filename.$BACKUP_DATE" 2>/dev/null || true
        fi
    done
fi

# Método 2: Backup directo del volumen Docker
if sudo docker volume inspect "$VOLUME_NAME" &>/dev/null; then
    echo "📦 Método 2: Backup directo del volumen Docker..."
    
    # Crear contenedor temporal para acceder al volumen
    TEMP_CONTAINER="backup-temp-$$"
    
    # Limpiar contenedor temporal si existe
    sudo docker rm -f "$TEMP_CONTAINER" 2>/dev/null || true
    
    # Crear contenedor temporal con el volumen montado
    sudo docker run --rm \
        -v "$VOLUME_NAME:/data" \
        -v "$(pwd)/$BACKUP_DIR:/backup" \
        alpine:latest \
        sh -c "cp -r /data/* /backup/volume-backup-$BACKUP_DATE/ 2>/dev/null || true && ls -la /backup/volume-backup-$BACKUP_DATE/ || echo 'Volumen vacío o sin permisos'"
    
    if [ -d "$BACKUP_DIR/volume-backup-$BACKUP_DATE" ]; then
        echo "   ✅ Backup del volumen creado: $BACKUP_DIR/volume-backup-$BACKUP_DATE"
    else
        echo "   ⚠️  No se pudo crear backup del volumen (puede estar vacío)"
    fi
else
    echo "   ⚠️  Volumen $VOLUME_NAME no existe aún"
fi

# Crear archivo de información del backup
INFO_FILE="$BACKUP_DIR/backup-info-$BACKUP_DATE.txt"
{
    echo "=== Información del Backup ==="
    echo "Fecha: $(date)"
    echo "Contenedor: $CONTAINER_NAME"
    echo "Volumen: $VOLUME_NAME"
    echo ""
    echo "=== Estado del Contenedor ==="
    sudo docker ps -a -f name="$CONTAINER_NAME" || echo "Contenedor no encontrado"
    echo ""
    echo "=== Estado del Volumen ==="
    sudo docker volume inspect "$VOLUME_NAME" 2>/dev/null || echo "Volumen no encontrado"
    echo ""
    echo "=== Archivos en el Backup ==="
    ls -lh "$BACKUP_DIR"/*"$BACKUP_DATE"* 2>/dev/null || echo "No hay archivos de backup"
} > "$INFO_FILE"

echo ""
echo "✅ Backup completado!"
echo "📁 Ubicación: $BACKUP_DIR"
echo "📄 Información: $INFO_FILE"
echo ""
echo "Archivos creados:"
ls -lh "$BACKUP_DIR"/*"$BACKUP_DATE"* 2>/dev/null || echo "  (ninguno)"

