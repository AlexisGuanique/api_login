#!/usr/bin/env python3
"""
Script para limpiar emails completados antiguos automáticamente.
Se ejecuta cada 7 días y elimina emails completados con más de 7 días de antigüedad.
"""

import os
import sys
import logging
from datetime import datetime, timedelta

# Agregar el directorio del proyecto al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.email import Email

# Configurar logging
def setup_logging():
    """Configura el sistema de logging para el script."""
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, 'email_cleanup.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)

def cleanup_old_completed_emails(days_old=7, dry_run=False):
    """
    Elimina emails completados más antiguos que days_old días.
    
    Args:
        days_old (int): Días de antigüedad para considerar emails como "antiguos"
        dry_run (bool): Si es True, solo muestra qué se eliminaría sin hacer cambios
    
    Returns:
        int: Número de emails eliminados, o -1 si hubo error
    """
    logger = logging.getLogger(__name__)
    app = create_app()
    
    with app.app_context():
        try:
            # Calcular fecha límite
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            logger.info(f"Iniciando limpieza de emails completados (más antiguos que {days_old} días)")
            logger.info(f"Fecha límite: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Buscar emails completados antiguos
            old_emails = Email.query.filter(
                Email.status == 'completed',
                Email.created_at < cutoff_date
            ).all()
            
            if not old_emails:
                logger.info(f"No hay emails completados antiguos para limpiar (más de {days_old} días)")
                return 0
            
            logger.info(f"Encontrados {len(old_emails)} emails completados antiguos")
            
            if dry_run:
                logger.info("MODO DRY RUN - No se eliminarán emails")
                # Mostrar algunos ejemplos
                for i, email in enumerate(old_emails[:5]):
                    days_old_calc = (datetime.utcnow() - email.created_at).days
                    logger.info(f"  {i+1}. ID {email.id}: {email.email} (creado hace {days_old_calc} días)")
                if len(old_emails) > 5:
                    logger.info(f"  ... y {len(old_emails) - 5} más")
                return len(old_emails)
            
            # Eliminar emails
            email_ids = [email.id for email in old_emails]
            deleted_count = Email.query.filter(Email.id.in_(email_ids)).delete(synchronize_session=False)
            db.session.commit()
            
            logger.info(f"✅ Limpieza completada: {deleted_count} emails eliminados")
            
            # Estadísticas adicionales
            remaining_emails = Email.query.filter(Email.status == 'completed').count()
            logger.info(f"Emails completados restantes: {remaining_emails}")
            
            return deleted_count
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Error durante la limpieza: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return -1

def get_database_stats():
    """Obtiene estadísticas de la base de datos para logging."""
    logger = logging.getLogger(__name__)
    app = create_app()
    
    with app.app_context():
        try:
            total_emails = Email.query.count()
            completed_emails = Email.query.filter(Email.status == 'completed').count()
            active_emails = Email.query.filter(Email.status == 'active').count()
            
            # Emails por usage_count
            usage_0 = Email.query.filter(Email.usage_count == 0).count()
            usage_1 = Email.query.filter(Email.usage_count == 1).count()
            usage_2 = Email.query.filter(Email.usage_count == 2).count()
            
            logger.info("📊 Estadísticas de la base de datos:")
            logger.info(f"  Total emails: {total_emails}")
            logger.info(f"  Activos: {active_emails}")
            logger.info(f"  Completados: {completed_emails}")
            logger.info(f"  Usage 0: {usage_0}")
            logger.info(f"  Usage 1: {usage_1}")
            logger.info(f"  Usage 2: {usage_2}")
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")

if __name__ == "__main__":
    # Configurar logging
    logger = setup_logging()
    
    logger.info("=" * 60)
    logger.info("INICIANDO SCRIPT DE LIMPIEZA DE EMAILS")
    logger.info("=" * 60)
    
    # Obtener configuración
    days_old = int(os.getenv('CLEANUP_DAYS', 7))
    dry_run = os.getenv('DRY_RUN', 'false').lower() == 'true'
    
    logger.info(f"Configuración: days_old={days_old}, dry_run={dry_run}")
    
    # Mostrar estadísticas antes de la limpieza
    get_database_stats()
    
    # Ejecutar limpieza
    result = cleanup_old_completed_emails(days_old, dry_run)
    
    if result >= 0:
        logger.info(f"✅ Script completado exitosamente. Emails procesados: {result}")
        sys.exit(0)
    else:
        logger.error("❌ Script falló con errores")
        sys.exit(1)
