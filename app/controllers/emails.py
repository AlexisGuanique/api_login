import jwt
import os
import re
import random

from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from app.models.email import Email
from app.models.user import User
from app.database import db
from app.utils.auth import token_required
from sqlalchemy import func

emails_bp = Blueprint('emails', __name__, url_prefix='/api/emails')

# Constante para el tamaño del lote (SQLite tiene límite de ~999 parámetros)
BATCH_SIZE = 500  # Usar 500 para estar seguros, dejando margen

def process_batch_updates(email_ids, update_dict):
    """
    Procesa actualizaciones en lotes para evitar exceder límites de SQLite.
    
    Args:
        email_ids: Lista de IDs de emails a actualizar
        update_dict: Diccionario con los campos a actualizar
        
    Returns:
        Número total de registros actualizados
    """
    total_updated = 0
    for i in range(0, len(email_ids), BATCH_SIZE):
        batch_ids = email_ids[i:i + BATCH_SIZE]
        updated = db.session.query(Email).filter(Email.id.in_(batch_ids)).update(
            update_dict, 
            synchronize_session=False
        )
        total_updated += updated
    return total_updated

def process_batch_deletes(email_ids):
    """
    Procesa eliminaciones en lotes para evitar exceder límites de SQLite.
    
    Args:
        email_ids: Lista de IDs de emails a eliminar
        
    Returns:
        Número total de registros eliminados
    """
    total_deleted = 0
    for i in range(0, len(email_ids), BATCH_SIZE):
        batch_ids = email_ids[i:i + BATCH_SIZE]
        deleted = Email.query.filter(Email.id.in_(batch_ids)).delete(synchronize_session=False)
        total_deleted += deleted
    return total_deleted

#! ENDPOINT PARA OBTENER TODOS LOS EMAILS (Solo Admin)
@emails_bp.route('/', methods=['GET'])
def get_all_emails():
    admin_key = request.headers.get('Admin-Key')

    # Verificar si el Admin-Key es válido
    if admin_key != os.getenv('ADMIN_KEY'):
        return jsonify({"error": "Acceso no autorizado"}), 403

    # Obtener todos los emails de la base de datos
    emails = Email.query.all()

    # Formatear la lista de emails para la respuesta
    emails_list = [
        {
            "id": email.id,
            "email": email.email,
            "user_id": email.user_id,
            "user_username": email.user.username if email.user else None,
            "usage_count": email.usage_count,
            "status": email.status,
            "created_at": email.created_at.isoformat() if email.created_at else None
        }
        for email in emails
    ]

    # Respuesta final
    return jsonify({
        "message": "Emails obtenidos exitosamente",
        "emails": emails_list,
        "count": len(emails_list)
    }), 200


#! ENDPOINT PARA OBTENER EMAILS DE UN USUARIO ESPECÍFICO
@emails_bp.route('/user/<int:user_id>', methods=['POST'])
@token_required
def get_user_emails(user_id):
    # Obtener todos los emails del usuario
    user_emails = Email.query.filter_by(user_id=user_id).all()

    # Formatear la lista de emails para la respuesta
    emails_list = [
        {
            "id": email.id,
            "email": email.email,
            "user_id": email.user_id,
            "usage_count": email.usage_count,
            "status": email.status,
            "created_at": email.created_at.isoformat() if email.created_at else None
        }
        for email in user_emails
    ]

    return jsonify({
        "message": "Emails del usuario obtenidos exitosamente",
        "user_id": user_id,
        "emails": emails_list,
        "count": len(emails_list)
    }), 200


#! ENDPOINT PARA GUARDAR EMAILS (UNO O MÚLTIPLES)
@emails_bp.route('/save/<int:user_id>', methods=['POST'])
@token_required
def save_emails(user_id):
    # Obtener datos del body
    data = request.json
    
    # Obtener emails del body (puede ser string o lista)
    emails_data = data.get('emails') or data.get('email')
    
    if not emails_data:
        return jsonify({"error": "Dominio(s) de email requerido(s) (formato: @dominio.com)"}), 400
    
    # Convertir a lista si es un string único
    if isinstance(emails_data, str):
        emails_list = [emails_data]
    elif isinstance(emails_data, list):
        emails_list = emails_data
    else:
        return jsonify({"error": "Formato inválido. Debe ser string o lista de strings"}), 400
    
    # Validar que todos los elementos sean strings
    if not all(isinstance(email, str) for email in emails_list):
        return jsonify({"error": "Todos los dominios deben ser strings"}), 400
    
    # Validar formato de cada dominio (debe empezar con @ y tener formato válido)
    domain_pattern = r'^@[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$'
    invalid_emails = []
    valid_emails = []
    
    for email in emails_list:
        if not re.match(domain_pattern, email):
            invalid_emails.append(email)
        else:
            valid_emails.append(email)
    
    # Mantener todos los emails, incluyendo duplicados
    original_count = len(emails_list)
    duplicates_removed = 0  # No eliminamos duplicados
    
    # Determinar si el usuario permite 2 usos (solo usuario ID 3)
    allows_two_uses = (user_id == 3)
    
    # Procesar cada email individualmente (incluyendo duplicados)
    new_emails_list = []
    available_emails_list = []  # Emails disponibles para usar
    completed_emails_list = []  # Emails completados que se van a reiniciar (status = 'completed')
    
    for email_address in emails_list:
        # Buscar si existe un email con este dominio para este usuario
        existing_email = Email.query.filter(
            Email.email == email_address,
            Email.user_id == user_id
        ).first()
        
        if existing_email:
            if existing_email.status == 'completed':
                # Email completado - reiniciar completamente
                completed_emails_list.append(email_address)
            elif existing_email.status == 'active':
                # Email activo - verificar si está disponible según el tipo de usuario
                if allows_two_uses:
                    # Usuario 3: disponible si usage_count = 0 o 1
                    if existing_email.usage_count in [0, 1]:
                        available_emails_list.append(email_address)
                else:
                    # Otros usuarios: disponible solo si usage_count = 0
                    if existing_email.usage_count == 0:
                        available_emails_list.append(email_address)
        else:
            new_emails_list.append(email_address)
    
    # Crear nuevos emails para cada instancia (incluyendo duplicados)
    new_emails = []
    restarted_emails = []
    try:
        # Crear emails nuevos (uno por cada instancia)
        for email_address in new_emails_list:
            new_email = Email(
                email=email_address,
                user_id=user_id,
                usage_count=0,
                status='active'
            )
            new_emails.append(new_email)
            db.session.add(new_email)
        
        # Reiniciar emails completados (uno por cada instancia)
        for email_address in completed_emails_list:
            existing_email = Email.query.filter(
                Email.email == email_address,
                Email.user_id == user_id
            ).first()
            # Reiniciar desde completado: status = 'active', usage_count = 0 (disponible para usar)
            # Para usuario 3, esto permite 2 usos nuevamente
            # Para otros usuarios, permite 1 uso
            existing_email.status = 'active'
            existing_email.usage_count = 0
            restarted_emails.append(email_address)
        
        db.session.commit()
        
        # Preparar mensaje según el resultado
        total_processed = len(new_emails) + len(restarted_emails) + len(available_emails_list)
        
        message_parts = []
        if len(new_emails) > 0:
            message_parts.append(f"{len(new_emails)} nuevo(s)")
        if len(restarted_emails) > 0:
            message_parts.append(f"{len(restarted_emails)} reiniciado(s) desde completados (disponible para usar)")
        if len(available_emails_list) > 0:
            message_parts.append(f"{len(available_emails_list)} ya disponible(s)")
        if duplicates_removed > 0:
            message_parts.append(f"{duplicates_removed} duplicado(s) eliminado(s)")
        
        if len(message_parts) > 1:
            message = f"Procesamiento completado: {', '.join(message_parts)}"
        elif len(message_parts) == 1:
            message = f"Procesamiento completado: {message_parts[0]}"
        else:
            message = "No se procesaron emails"
        
        response_data = {
            "message": message,
            "saved_count": len(new_emails),
            "restarted_count": len(restarted_emails),
            "available_count": len(available_emails_list),
            "invalid_format_count": len(invalid_emails),
            "duplicates_removed": duplicates_removed,
            "total_processed": len(emails_list)
        }
        
        # Agregar emails reiniciados si hay alguno
        if restarted_emails:
            response_data["restarted_emails"] = restarted_emails
        
        # Agregar emails disponibles si hay alguno
        if available_emails_list:
            response_data["available_emails"] = available_emails_list
        
        # Agregar emails con formato inválido si hay alguno
        if invalid_emails:
            response_data["invalid_format_emails"] = invalid_emails
        
        # Código de estado según el resultado
        status_code = 201 if (new_emails_list or restarted_emails) else 200
        
        return jsonify(response_data), status_code
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al guardar los emails: {str(e)}"}), 500


#! ENDPOINT PARA OBTENER EMAILS DISPONIBLES DE UN USUARIO
# Usuario ID 3: usage_count = 0 o 1 y status = 'active' (permite 2 usos)
# Otros usuarios: usage_count = 0 y status = 'active' (solo 1 uso)
@emails_bp.route('/available/<int:user_id>', methods=['POST'])
def get_available_emails(user_id):
    try:
        # Obtener access_token del body
        data = request.json or {}
        access_token = data.get('access_token')
        
        if not access_token:
            return jsonify({"error": "Access token requerido"}), 400
        
        # Verificar el token
        try:
            # Decodificar sin verificar exp automáticamente - la verificación real se hace con token_expiration
            token_data = jwt.decode(
                access_token, 
                current_app.config['SECRET_KEY'], 
                algorithms=['HS256'],
                options={"verify_exp": False}
            )
            token_username = token_data.get('username')
            
            # Buscar el usuario por username para obtener su ID
            user = User.query.filter_by(username=token_username).first()
            if not user:
                return jsonify({"error": "Usuario no encontrado"}), 401
            
            # Verificar que el token pertenece al usuario solicitado
            if user.id != user_id:
                return jsonify({"error": "Token no válido para este usuario"}), 401
            
            # Verificar si el token ha expirado según la base de datos (fuente de verdad)
            if user.token_expiration and datetime.utcnow() > user.token_expiration:
                return jsonify({"error": "Token expirado"}), 401
                
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token inválido"}), 401
        
        # Determinar si el usuario permite 2 usos (solo usuario ID 3)
        allows_two_uses = (user_id == 3)
        
        # Obtener emails disponibles según el tipo de usuario
        if allows_two_uses:
            # Usuario 3: emails con usage_count = 0 o 1 y status = 'active' (permite 2 usos)
            available_emails = Email.query.filter(
                Email.user_id == user_id,
                Email.status == 'active',
                Email.usage_count.in_([0, 1])
            ).order_by(Email.created_at.asc()).all()
        else:
            # Otros usuarios: solo emails con usage_count = 0 y status = 'active' (solo 1 uso)
            available_emails = Email.query.filter(
                Email.user_id == user_id,
                Email.status == 'active',
                Email.usage_count == 0
            ).order_by(Email.created_at.asc()).all()
        
        # Formatear la lista de emails para la respuesta
        emails_list = [
            {
                "id": email.id,
                "email": email.email,
                "user_id": email.user_id,
                "usage_count": email.usage_count,
                "created_at": email.created_at.isoformat() if email.created_at else None
            }
            for email in available_emails
        ]
        
        return jsonify({
            "message": "Dominios disponibles obtenidos exitosamente",
            "user_id": user_id,
            "emails": emails_list,
            "count": len(emails_list)
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al obtener los dominios disponibles: {str(e)}"}), 500


#! ENDPOINT PARA LIMPIAR EMAILS COMPLETADOS ANTIGUOS
@emails_bp.route('/cleanup/<int:user_id>', methods=['POST'])
def cleanup_completed_emails(user_id):
    try:
        # Obtener access_token del body
        data = request.json or {}
        access_token = data.get('access_token')
        
        if not access_token:
            return jsonify({"error": "Access token requerido"}), 400
        
        # Verificar el token
        try:
            # Decodificar sin verificar exp automáticamente - la verificación real se hace con token_expiration
            token_data = jwt.decode(
                access_token, 
                current_app.config['SECRET_KEY'], 
                algorithms=['HS256'],
                options={"verify_exp": False}
            )
            token_username = token_data.get('username')
            
            # Buscar el usuario por username para obtener su ID
            user = User.query.filter_by(username=token_username).first()
            if not user:
                return jsonify({"error": "Usuario no encontrado"}), 401
            
            # Verificar que el token pertenece al usuario solicitado
            if user.id != user_id:
                return jsonify({"error": "Token no válido para este usuario"}), 401
            
            # Verificar si el token ha expirado según la base de datos (fuente de verdad)
            if user.token_expiration and datetime.utcnow() > user.token_expiration:
                return jsonify({"error": "Token expirado"}), 401
                
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token inválido"}), 401
        
        # Obtener parámetros de limpieza
        days_old = data.get('days_old', 7)  # Por defecto, eliminar emails completados de hace 7 días
        dry_run = data.get('dry_run', False)  # Por defecto, hacer limpieza real
        
        if not isinstance(days_old, int) or days_old < 1:
            return jsonify({"error": "days_old debe ser un número entero positivo"}), 400
        
        # Calcular fecha límite
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Buscar emails completados antiguos
        old_completed_emails = Email.query.filter(
            Email.user_id == user_id,
            Email.status == 'completed',
            Email.created_at < cutoff_date
        ).all()
        
        if not old_completed_emails:
            return jsonify({
                "message": "No hay emails completados antiguos para limpiar",
                "user_id": user_id,
                "days_old": days_old,
                "cutoff_date": cutoff_date.isoformat(),
                "deleted_count": 0
            }), 200
        
        if dry_run:
            # Solo mostrar qué se eliminaría
            emails_to_delete = [
                {
                    "id": email.id,
                    "email": email.email,
                    "created_at": email.created_at.isoformat(),
                    "days_old": (datetime.utcnow() - email.created_at).days
                }
                for email in old_completed_emails
            ]
            
            return jsonify({
                "message": f"DRY RUN: Se eliminarían {len(old_completed_emails)} emails completados",
                "user_id": user_id,
                "days_old": days_old,
                "cutoff_date": cutoff_date.isoformat(),
                "emails_to_delete": emails_to_delete[:10],  # Mostrar solo los primeros 10
                "total_to_delete": len(old_completed_emails)
            }), 200
        
        # Eliminar emails completados antiguos
        # Usar procesamiento por lotes para evitar exceder límites de SQLite
        email_ids = [email.id for email in old_completed_emails]
        deleted_count = process_batch_deletes(email_ids)
        db.session.commit()
        
        return jsonify({
            "message": f"Limpieza completada exitosamente",
            "user_id": user_id,
            "days_old": days_old,
            "cutoff_date": cutoff_date.isoformat(),
            "deleted_count": deleted_count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error durante la limpieza: {str(e)}"}), 500


#! ENDPOINT PARA ROTAR EMAILS COMPLETADOS (REINICIAR A DISPONIBLES)
@emails_bp.route('/rotate/<int:user_id>', methods=['POST'])
def rotate_completed_emails(user_id):
    try:
        # Obtener access_token del body
        data = request.json or {}
        access_token = data.get('access_token')
        
        if not access_token:
            return jsonify({"error": "Access token requerido"}), 400
        
        # Verificar el token
        try:
            # Decodificar sin verificar exp automáticamente - la verificación real se hace con token_expiration
            token_data = jwt.decode(
                access_token, 
                current_app.config['SECRET_KEY'], 
                algorithms=['HS256'],
                options={"verify_exp": False}
            )
            token_username = token_data.get('username')
            
            # Buscar el usuario por username para obtener su ID
            user = User.query.filter_by(username=token_username).first()
            if not user:
                return jsonify({"error": "Usuario no encontrado"}), 401
            
            # Verificar que el token pertenece al usuario solicitado
            if user.id != user_id:
                return jsonify({"error": "Token no válido para este usuario"}), 401
            
            # Verificar si el token ha expirado según la base de datos (fuente de verdad)
            if user.token_expiration and datetime.utcnow() > user.token_expiration:
                return jsonify({"error": "Token expirado"}), 401
                
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token inválido"}), 401
        
        # Obtener parámetros
        max_rotate = data.get('max_rotate', 100)  # Máximo emails a rotar por petición
        
        if not isinstance(max_rotate, int) or max_rotate < 1:
            return jsonify({"error": "max_rotate debe ser un número entero positivo"}), 400
        
        # Buscar emails completados para rotar
        completed_emails = Email.query.filter(
            Email.user_id == user_id,
            Email.status == 'completed'
        ).order_by(Email.created_at.asc()).limit(max_rotate).all()
        
        if not completed_emails:
            return jsonify({
                "message": "No hay emails completados para rotar",
                "user_id": user_id,
                "rotated_count": 0
            }), 200
        
        # Rotar emails: status = 'active', usage_count = 1
        rotated_count = 0
        for email in completed_emails:
            email.status = 'active'
            email.usage_count = 1  # Disponible para un uso más
            rotated_count += 1
        
        db.session.commit()
        
        return jsonify({
            "message": f"Rotación completada exitosamente",
            "user_id": user_id,
            "rotated_count": rotated_count,
            "emails_rotated": [
                {
                    "id": email.id,
                    "email": email.email,
                    "new_status": "active",
                    "new_usage_count": 1
                }
                for email in completed_emails[:10]  # Mostrar solo los primeros 10
            ]
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error durante la rotación: {str(e)}"}), 500


#! ENDPOINT PARA LIMPIAR EMAILS COMPLETADOS ANTIGUOS (MÁS DE 7 DÍAS)
@emails_bp.route('/cleanup-old/<int:user_id>', methods=['POST'])
def cleanup_old_completed_emails(user_id):
    try:
        # Obtener access_token del body
        data = request.json or {}
        access_token = data.get('access_token')
        
        if not access_token:
            return jsonify({"error": "Access token requerido"}), 400
        
        # Verificar el token
        try:
            # Decodificar sin verificar exp automáticamente - la verificación real se hace con token_expiration
            token_data = jwt.decode(
                access_token, 
                current_app.config['SECRET_KEY'], 
                algorithms=['HS256'],
                options={"verify_exp": False}
            )
            token_username = token_data.get('username')
            
            # Buscar el usuario por username para obtener su ID
            user = User.query.filter_by(username=token_username).first()
            if not user:
                return jsonify({"error": "Usuario no encontrado"}), 401
            
            # Verificar que el token pertenece al usuario solicitado
            if user.id != user_id:
                return jsonify({"error": "Token no válido para este usuario"}), 401
            
            # Verificar si el token ha expirado según la base de datos (fuente de verdad)
            if user.token_expiration and datetime.utcnow() > user.token_expiration:
                return jsonify({"error": "Token expirado"}), 401
                
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token inválido"}), 401
        
        # Obtener parámetros
        days_old = data.get('days_old', 7)  # Por defecto 7 días
        
        # Permitir 0 días (limpiar emails de ayer y anteriores) y -1 para emails de hoy
        if not isinstance(days_old, int) or days_old < -1:
            return jsonify({"error": "days_old debe ser un número entero >= -1 (0=ayer y anteriores, -1=hoy, 1+=días atrás)"}), 400
        
        # Calcular fecha límite
        now = datetime.utcnow()
        
        if days_old == -1:
            # Limpiar emails de hoy (desde inicio del día hasta ahora)
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            old_completed_emails = Email.query.filter(
                Email.user_id == user_id,
                Email.status == 'completed',
                Email.created_at >= start_of_day,
                Email.created_at <= now
            ).all()
        else:
            # Limpiar emails más antiguos que days_old días
            cutoff_date = now - timedelta(days=days_old)
            old_completed_emails = Email.query.filter(
                Email.user_id == user_id,
                Email.status == 'completed',
                Email.created_at < cutoff_date
            ).all()
        
        if not old_completed_emails:
            # Determinar el mensaje según el tipo de limpieza
            if days_old == -1:
                message = "No hay emails completados de hoy para limpiar"
                date_info = f"desde {start_of_day.isoformat()} hasta {now.isoformat()}"
            else:
                message = "No hay emails completados antiguos para limpiar"
                date_info = f"anteriores a {cutoff_date.isoformat()}"
            
            return jsonify({
                "message": message,
                "user_id": user_id,
                "days_old": days_old,
                "date_range": date_info,
                "deleted_count": 0,
                "emails_before": {
                    "total": Email.query.filter_by(user_id=user_id).count(),
                    "completed": Email.query.filter_by(user_id=user_id, status='completed').count(),
                    "active": Email.query.filter_by(user_id=user_id, status='active').count()
                }
            }), 200
        
        # Eliminar emails completados antiguos
        # Usar procesamiento por lotes para evitar exceder límites de SQLite
        email_ids = [email.id for email in old_completed_emails]
        deleted_count = process_batch_deletes(email_ids)
        db.session.commit()
        
        # Estadísticas después de la limpieza
        stats_after = {
            "total": Email.query.filter_by(user_id=user_id).count(),
            "completed": Email.query.filter_by(user_id=user_id, status='completed').count(),
            "active": Email.query.filter_by(user_id=user_id, status='active').count()
        }
        
        # Determinar información de fecha para el mensaje de éxito
        if days_old == -1:
            date_info = f"desde {start_of_day.isoformat()} hasta {now.isoformat()}"
        else:
            date_info = f"anteriores a {cutoff_date.isoformat()}"
        
        return jsonify({
            "message": f"Limpieza completada exitosamente",
            "user_id": user_id,
            "days_old": days_old,
            "date_range": date_info,
            "deleted_count": deleted_count,
            "emails_before": {
                "total": stats_after["total"] + deleted_count,
                "completed": stats_after["completed"] + deleted_count,
                "active": stats_after["active"]
            },
            "emails_after": stats_after,
            "space_freed": f"{deleted_count} emails eliminados"
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error durante la limpieza: {str(e)}"}), 500


#! ENDPOINT PARA VER ESTADÍSTICAS DE LIMPIEZA (ANTES DE LIMPIAR)
@emails_bp.route('/cleanup-stats/<int:user_id>', methods=['POST'])
def get_cleanup_stats(user_id):
    try:
        # Obtener access_token del body
        data = request.json or {}
        access_token = data.get('access_token')
        
        if not access_token:
            return jsonify({"error": "Access token requerido"}), 400
        
        # Verificar el token
        try:
            # Decodificar sin verificar exp automáticamente - la verificación real se hace con token_expiration
            token_data = jwt.decode(
                access_token, 
                current_app.config['SECRET_KEY'], 
                algorithms=['HS256'],
                options={"verify_exp": False}
            )
            token_username = token_data.get('username')
            
            # Buscar el usuario por username para obtener su ID
            user = User.query.filter_by(username=token_username).first()
            if not user:
                return jsonify({"error": "Usuario no encontrado"}), 401
            
            # Verificar que el token pertenece al usuario solicitado
            if user.id != user_id:
                return jsonify({"error": "Token no válido para este usuario"}), 401
            
            # Verificar si el token ha expirado según la base de datos (fuente de verdad)
            if user.token_expiration and datetime.utcnow() > user.token_expiration:
                return jsonify({"error": "Token expirado"}), 401
                
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token inválido"}), 401
        
        # Obtener parámetros
        days_old = data.get('days_old', 7)  # Por defecto 7 días
        
        if not isinstance(days_old, int) or days_old < 1:
            return jsonify({"error": "days_old debe ser un número entero positivo"}), 400
        
        # Calcular fecha límite
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Estadísticas generales
        total_emails = Email.query.filter_by(user_id=user_id).count()
        completed_emails = Email.query.filter_by(user_id=user_id, status='completed').count()
        active_emails = Email.query.filter_by(user_id=user_id, status='active').count()
        
        # Emails por usage_count
        usage_0 = Email.query.filter_by(user_id=user_id, usage_count=0).count()
        usage_1 = Email.query.filter_by(user_id=user_id, usage_count=1).count()
        usage_2 = Email.query.filter_by(user_id=user_id, usage_count=2).count()
        
        # Emails completados antiguos (que se eliminarían)
        old_completed_emails = Email.query.filter(
            Email.user_id == user_id,
            Email.status == 'completed',
            Email.created_at < cutoff_date
        ).all()
        
        # Estadísticas de emails antiguos
        old_emails_stats = []
        for email in old_completed_emails[:10]:  # Solo los primeros 10
            days_old_calc = (datetime.utcnow() - email.created_at).days
            old_emails_stats.append({
                "id": email.id,
                "email": email.email,
                "created_at": email.created_at.isoformat(),
                "days_old": days_old_calc
            })
        
        return jsonify({
            "message": "Estadísticas de limpieza obtenidas exitosamente",
            "user_id": user_id,
            "days_old": days_old,
            "cutoff_date": cutoff_date.isoformat(),
            "current_stats": {
                "total_emails": total_emails,
                "completed_emails": completed_emails,
                "active_emails": active_emails,
                "usage_breakdown": {
                    "usage_0": usage_0,
                    "usage_1": usage_1,
                    "usage_2": usage_2
                }
            },
            "cleanup_info": {
                "emails_to_delete": len(old_completed_emails),
                "space_to_free": f"{len(old_completed_emails)} emails",
                "emails_after_cleanup": {
                    "total": total_emails - len(old_completed_emails),
                    "completed": completed_emails - len(old_completed_emails),
                    "active": active_emails
                }
            },
            "sample_old_emails": old_emails_stats,
            "note": f"Se mostrarían {len(old_emails_stats)} de {len(old_completed_emails)} emails antiguos"
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error obteniendo estadísticas: {str(e)}"}), 500


#! ENDPOINT PARA OBTENER EMAILS USADOS DE UN USUARIO (status = 'completed')
@emails_bp.route('/used/<int:user_id>', methods=['POST'])
@token_required
def get_used_emails(user_id):
    try:
        # Obtener emails usados (status = 'completed')
        used_emails = Email.query.filter(
            Email.user_id == user_id,
            Email.status == 'completed'
        ).order_by(Email.created_at.asc()).all()
        
        # Formatear la lista de emails para la respuesta
        emails_list = [
            {
                "id": email.id,
                "email": email.email,
                "user_id": email.user_id,
                "usage_count": email.usage_count,
                "created_at": email.created_at.isoformat() if email.created_at else None
            }
            for email in used_emails
        ]
        
        return jsonify({
            "message": "Emails usados obtenidos exitosamente",
            "user_id": user_id,
            "emails": emails_list,
            "count": len(emails_list)
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al obtener los emails usados: {str(e)}"}), 500


#! ENDPOINT PARA OBTENER CANTIDAD DE EMAILS DE UN USUARIO
@emails_bp.route('/count/<int:user_id>', methods=['POST'])
@token_required
def get_email_count(user_id):
    try:
        # Determinar si el usuario permite 2 usos (solo usuario ID 3)
        allows_two_uses = (user_id == 3)
        
        # Contar emails del usuario por estado de uso y status
        total_count = db.session.query(Email).filter_by(user_id=user_id).count()
        
        # Emails disponibles según el tipo de usuario
        if allows_two_uses:
            # Usuario 3: emails con usage_count = 0 o 1 y status='active' (permite 2 usos)
            available_count = db.session.query(Email).filter(
                Email.user_id == user_id,
                Email.status == 'active',
                Email.usage_count.in_([0, 1])
            ).count()
        else:
            # Otros usuarios: solo emails con usage_count = 0 y status='active' (solo 1 uso)
            available_count = db.session.query(Email).filter(
                Email.user_id == user_id,
                Email.status == 'active',
                Email.usage_count == 0
            ).count()
        
        # Desglose detallado por usage_count
        no_usage_count = db.session.query(Email).filter(
            Email.user_id == user_id,
            Email.status == 'active',
            Email.usage_count == 0
        ).count()
        
        one_usage_count = db.session.query(Email).filter(
            Email.user_id == user_id,
            Email.status == 'active',
            Email.usage_count == 1
        ).count()
        
        completed_count = db.session.query(Email).filter_by(
            user_id=user_id, 
            status='completed'
        ).count()
        
        return jsonify({
            "message": "Cantidad de emails obtenida exitosamente",
            "user_id": user_id,
            "total_count": total_count,
            "available_count": available_count,  # Ahora incluye emails con 0 y 1 uso
            "completed_count": completed_count,
            "breakdown": {
                "sin_uso": no_usage_count,
                "con_1_uso": one_usage_count,
                "completados": completed_count,
                "disponibles": available_count  # Mantener compatibilidad
            }
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al obtener la cantidad de emails: {str(e)}"}), 500


#! ENDPOINT PARA OBTENER Y ELIMINAR EMAILS (UNO O MÚLTIPLES)
@emails_bp.route('/next/<int:user_id>', methods=['POST'])
@token_required
def get_next_emails(user_id):
    try:
        # Obtener datos del body
        data = request.json or {}
        
        # Obtener cantidad de emails a procesar (por defecto 1)
        count = data.get('count', 1)
        
        # Validar que count sea un número positivo
        if not isinstance(count, int) or count <= 0:
            return jsonify({"error": "El parámetro 'count' debe ser un número entero positivo"}), 400
        
        # Determinar si el usuario permite 2 usos (solo usuario ID 3)
        allows_two_uses = (user_id == 3)
        
        # Consulta optimizada: obtener emails activos disponibles
        # Usuario ID 3: status = 'active' y usage_count = 0 o 1 (permite 2 usos)
        # Otros usuarios: status = 'active' y usage_count = 0 (solo 1 uso)
        # Usar func.random() para asegurar aleatoriedad total, no emails consecutivos
        # with_for_update(skip_locked=True) previene condiciones de carrera
        if allows_two_uses:
            # Usuario 3: permitir emails con 0 o 1 uso
            emails = db.session.query(Email.id, Email.email, Email.created_at, Email.usage_count, Email.status).filter(
                Email.user_id == user_id,
                Email.status == 'active',
                Email.usage_count.in_([0, 1])
            ).order_by(func.random()).with_for_update(skip_locked=True).limit(count).all()
        else:
            # Otros usuarios: solo emails con 0 usos
            emails = db.session.query(Email.id, Email.email, Email.created_at, Email.usage_count, Email.status).filter(
                Email.user_id == user_id,
                Email.status == 'active',
                Email.usage_count == 0
            ).order_by(func.random()).with_for_update(skip_locked=True).limit(count).all()
        
        # Asegurar aleatoriedad adicional mezclando los resultados si hay múltiples emails
        # Esto garantiza que los emails no sean consecutivos incluso si la consulta los devuelve en cierto orden
        if len(emails) > 1:
            random.shuffle(emails)
        
        if not emails:
            return jsonify({
                "message": "No hay emails disponibles",
                "emails": [],
                "count": 0,
                "requested_count": count
            }), 200
        
        # Crear lista de emails para la respuesta y procesar actualizaciones
        emails_data = []
        emails_to_update_1_use = []  # Emails que pasarán de 0 a 1 uso
        emails_to_complete = []  # Emails que pasarán a completados
        
        for email in emails:
            current_usage = email.usage_count
            
            if allows_two_uses:
                # Usuario 3: permite 2 usos
                if current_usage == 0:
                    # Primer uso: incrementar a 1, mantener activo
                    new_usage = 1
                    new_status = 'active'
                    emails_to_update_1_use.append(email.id)
                elif current_usage == 1:
                    # Segundo uso: incrementar a 2, marcar como completado
                    new_usage = 2
                    new_status = 'completed'
                    emails_to_complete.append(email.id)
            else:
                # Otros usuarios: solo 1 uso, completar inmediatamente
                if current_usage == 0:
                    new_usage = 1
                    new_status = 'completed'
                    emails_to_complete.append(email.id)
            
            email_data = {
                'id': email.id,
                'email': email.email,
                'created_at': email.created_at.isoformat() if email.created_at else None,
                'user_id': user_id,
                'usage_count': new_usage,
                'status': new_status
            }
            emails_data.append(email_data)
        
        # Actualizar emails según su estado actual
        # Emails con primer uso (0 -> 1, mantener activo) - solo para usuario 3
        if emails_to_update_1_use:
            process_batch_updates(emails_to_update_1_use, {Email.usage_count: 1, Email.status: 'active'})
        
        # Emails que se completan (1 -> 2 para usuario 3, 0 -> 1 para otros usuarios)
        if emails_to_complete:
            if allows_two_uses:
                # Usuario 3: segundo uso (1 -> 2, completar)
                process_batch_updates(emails_to_complete, {Email.usage_count: 2, Email.status: 'completed'})
            else:
                # Otros usuarios: primer uso (0 -> 1, completar)
                process_batch_updates(emails_to_complete, {Email.usage_count: 1, Email.status: 'completed'})
        
        db.session.commit()
        
        # Mensaje según la cantidad procesada
        first_use_count = len(emails_to_update_1_use)
        completed_count = len(emails_to_complete)
        
        if len(emails_data) == 1:
            if allows_two_uses:
                if first_use_count == 1:
                    message = "Email obtenido (primer uso, aún disponible para un uso más)"
                else:
                    message = "Email obtenido y completado (segundo uso finalizado)"
            else:
                message = "Email obtenido y completado (uso finalizado)"
        else:
            message_parts = []
            if allows_two_uses and first_use_count > 0:
                message_parts.append(f"{first_use_count} primer uso")
            if completed_count > 0:
                if allows_two_uses:
                    message_parts.append(f"{completed_count} completado(s)")
                else:
                    message_parts.append(f"{completed_count} completado(s)")
            message = f"{len(emails_data)} emails obtenidos ({', '.join(message_parts)})"
        
        response_data = {
            "message": message,
            "emails": emails_data,
            "count": len(emails_data),
            "requested_count": count,
            "completed_count": completed_count
        }
        
        # Agregar información sobre primer uso solo para usuario 3
        if allows_two_uses:
            response_data["first_use_count"] = first_use_count
        
        # Si se pidieron más emails de los disponibles, agregar información
        if len(emails_data) < count:
            response_data["note"] = f"Solo se encontraron {len(emails_data)} emails de los {count} solicitados"
        
        return jsonify(response_data), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al obtener los emails: {str(e)}"}), 500


#! ENDPOINT PARA ELIMINAR EMAILS (ACTIVOS Y COMPLETADOS) - SOLO ADMIN
@emails_bp.route('/delete/<int:user_id>', methods=['POST'])
def delete_emails(user_id):
    try:
        # Verificar Admin-Key en headers
        admin_key = request.headers.get('Admin-Key')
        
        # Verificar si el Admin-Key es válido
        if admin_key != os.getenv('ADMIN_KEY'):
            return jsonify({"error": "Acceso no autorizado. Admin-Key requerido"}), 403
        
        # Obtener datos del body
        data = request.json or {}
        
        # Obtener parámetros
        count = data.get('count', 10)  # Por defecto eliminar 10 emails
        order = data.get('order', 'newest')  # Por defecto desde los más nuevos
        status_filter = data.get('status', 'all')  # Por defecto todos los estados
        usage_filter = data.get('usage_filter', None)  # Filtro por usage_count (opcional)
        
        # Validar parámetros
        if not isinstance(count, int) or count <= 0:
            return jsonify({"error": "El parámetro 'count' debe ser un número entero positivo"}), 400
        
        if order not in ['newest', 'oldest']:
            return jsonify({"error": "El parámetro 'order' debe ser 'newest' o 'oldest'"}), 400
        
        if status_filter not in ['all', 'active', 'completed']:
            return jsonify({"error": "El parámetro 'status' debe ser 'all', 'active' o 'completed'"}), 400
        
        # Validar filtro de usage_count
        if usage_filter is not None:
            if isinstance(usage_filter, int):
                # Filtro por valor específico
                if usage_filter < 0:
                    return jsonify({"error": "El parámetro 'usage_filter' debe ser un número entero >= 0"}), 400
            elif isinstance(usage_filter, dict):
                # Filtro por rango {min: X, max: Y}
                if 'min' not in usage_filter and 'max' not in usage_filter:
                    return jsonify({"error": "El parámetro 'usage_filter' debe ser un número entero o un objeto con 'min' y/o 'max'"}), 400
                if 'min' in usage_filter and (not isinstance(usage_filter['min'], int) or usage_filter['min'] < 0):
                    return jsonify({"error": "El parámetro 'usage_filter.min' debe ser un número entero >= 0"}), 400
                if 'max' in usage_filter and (not isinstance(usage_filter['max'], int) or usage_filter['max'] < 0):
                    return jsonify({"error": "El parámetro 'usage_filter.max' debe ser un número entero >= 0"}), 400
                if 'min' in usage_filter and 'max' in usage_filter and usage_filter['min'] > usage_filter['max']:
                    return jsonify({"error": "El parámetro 'usage_filter.min' no puede ser mayor que 'usage_filter.max'"}), 400
            else:
                return jsonify({"error": "El parámetro 'usage_filter' debe ser un número entero o un objeto con 'min' y/o 'max'"}), 400
        
        # Construir consulta base
        query = Email.query.filter_by(user_id=user_id)
        
        # Aplicar filtro de status si no es 'all'
        if status_filter != 'all':
            query = query.filter_by(status=status_filter)
        
        # Aplicar filtro de usage_count si se especifica
        if usage_filter is not None:
            if isinstance(usage_filter, int):
                # Filtro por valor específico
                query = query.filter_by(usage_count=usage_filter)
            elif isinstance(usage_filter, dict):
                # Filtro por rango
                if 'min' in usage_filter and 'max' in usage_filter:
                    query = query.filter(Email.usage_count >= usage_filter['min'], Email.usage_count <= usage_filter['max'])
                elif 'min' in usage_filter:
                    query = query.filter(Email.usage_count >= usage_filter['min'])
                elif 'max' in usage_filter:
                    query = query.filter(Email.usage_count <= usage_filter['max'])
        
        # Aplicar ordenamiento
        if order == 'newest':
            # Desde los más nuevos hacia atrás (descendente)
            query = query.order_by(Email.created_at.desc())
        else:  # oldest
            # Desde los más viejos hacia adelante (ascendente)
            query = query.order_by(Email.created_at.asc())
        
        # Obtener emails a eliminar
        emails_to_delete = query.limit(count).all()
        
        if not emails_to_delete:
            return jsonify({
                "message": "No hay emails para eliminar con los criterios especificados",
                "user_id": user_id,
                "count": count,
                "order": order,
                "status_filter": status_filter,
                "usage_filter": usage_filter,
                "deleted_count": 0
            }), 200
        
        # Obtener estadísticas antes de eliminar
        stats_before = {
            "total": Email.query.filter_by(user_id=user_id).count(),
            "active": Email.query.filter_by(user_id=user_id, status='active').count(),
            "completed": Email.query.filter_by(user_id=user_id, status='completed').count()
        }
        
        # Preparar información de emails a eliminar
        emails_info = []
        for email in emails_to_delete:
            emails_info.append({
                "id": email.id,
                "email": email.email,
                "status": email.status,
                "usage_count": email.usage_count,
                "created_at": email.created_at.isoformat() if email.created_at else None
            })
        
        # Eliminar emails
        # Usar procesamiento por lotes para evitar exceder límites de SQLite
        email_ids = [email.id for email in emails_to_delete]
        deleted_count = process_batch_deletes(email_ids)
        db.session.commit()
        
        # Obtener estadísticas después de eliminar
        stats_after = {
            "total": Email.query.filter_by(user_id=user_id).count(),
            "active": Email.query.filter_by(user_id=user_id, status='active').count(),
            "completed": Email.query.filter_by(user_id=user_id, status='completed').count()
        }
        
        # Determinar mensaje según el orden
        order_text = "más nuevos hacia atrás" if order == 'newest' else "más viejos hacia adelante"
        status_text = "todos los estados" if status_filter == 'all' else f"estado '{status_filter}'"
        
        # Determinar texto del filtro de uso
        if usage_filter is None:
            usage_text = "cualquier uso"
        elif isinstance(usage_filter, int):
            usage_text = f"uso {usage_filter}"
        elif isinstance(usage_filter, dict):
            if 'min' in usage_filter and 'max' in usage_filter:
                usage_text = f"uso entre {usage_filter['min']} y {usage_filter['max']}"
            elif 'min' in usage_filter:
                usage_text = f"uso >= {usage_filter['min']}"
            elif 'max' in usage_filter:
                usage_text = f"uso <= {usage_filter['max']}"
        else:
            usage_text = "cualquier uso"
        
        return jsonify({
            "message": f"Eliminación completada exitosamente",
            "user_id": user_id,
            "deleted_count": deleted_count,
            "requested_count": count,
            "order": order,
            "status_filter": status_filter,
            "usage_filter": usage_filter,
            "description": f"Se eliminaron {deleted_count} emails desde los {order_text} con {status_text} y {usage_text}",
            "emails_deleted": emails_info[:20],  # Mostrar solo los primeros 20
            "total_emails_deleted": len(emails_info),
            "stats_before": stats_before,
            "stats_after": stats_after,
            "space_freed": f"{deleted_count} emails eliminados"
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error durante la eliminación: {str(e)}"}), 500


#! ENDPOINT PARA CORREGIR EMAILS INCONSISTENTES (usage_count = 1 y status = 'active')
@emails_bp.route('/fix-inconsistent/<int:user_id>', methods=['POST'])
def fix_inconsistent_emails(user_id):
    try:
        # Verificar Admin-Key en headers
        admin_key = request.headers.get('Admin-Key')
        
        # Verificar si el Admin-Key es válido
        if admin_key != os.getenv('ADMIN_KEY'):
            return jsonify({"error": "Acceso no autorizado. Admin-Key requerido"}), 403
        
        # Buscar emails inconsistentes (usage_count = 1 y status = 'active')
        # Con 1 uso, emails con usage_count = 1 y status='active' son inconsistentes (deberían estar completed)
        inconsistent_emails = Email.query.filter(
            Email.user_id == user_id,
            Email.usage_count == 1,
            Email.status == 'active'
        ).all()
        
        if not inconsistent_emails:
            return jsonify({
                "message": "No hay emails inconsistentes para corregir",
                "user_id": user_id,
                "fixed_count": 0
            }), 200
        
        # Corregir emails inconsistentes: marcar como 'completed'
        fixed_count = 0
        fixed_emails = []
        
        for email in inconsistent_emails:
            email.status = 'completed'
            fixed_emails.append({
                "id": email.id,
                "email": email.email,
                "old_status": "active",
                "new_status": "completed",
                "usage_count": email.usage_count,
                "created_at": email.created_at.isoformat() if email.created_at else None
            })
            fixed_count += 1
        
        db.session.commit()
        
        return jsonify({
            "message": f"Corrección completada exitosamente",
            "user_id": user_id,
            "fixed_count": fixed_count,
            "emails_fixed": fixed_emails[:20],  # Mostrar solo los primeros 20
            "total_emails_fixed": len(fixed_emails),
            "note": "Emails con usage_count = 1 y status='active' ahora tienen status = 'completed'"
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error durante la corrección: {str(e)}"}), 500


#! ENDPOINT PARA RESETEAR EMAILS COMPLETADOS A DISPONIBLES (CAMBIAR DE COMPLETED A ACTIVE)
@emails_bp.route('/reset-to-2-uses', methods=['POST'])
def reset_emails_to_2_uses():
    try:
        # Verificar Admin-Key en headers
        admin_key = request.headers.get('Admin-Key')
        
        # Verificar si el Admin-Key es válido
        if admin_key != os.getenv('ADMIN_KEY'):
            return jsonify({"error": "Acceso no autorizado. Admin-Key requerido"}), 403
        
        # Obtener datos del body
        data = request.json or {}
        
        # Obtener parámetros
        target_user_id = data.get('user_id', 3)  # Por defecto usuario ID 3
        reset_all_users = data.get('reset_all_users', False)  # Por defecto solo el usuario especificado
        include_2_uses = data.get('include_2_uses', False)  # Incluir emails con 2 usos completados (solo usuario 3)
        
        # Validar parámetros
        if not isinstance(target_user_id, int) or target_user_id < 1:
            return jsonify({"error": "El parámetro 'user_id' debe ser un número entero positivo"}), 400
        
        if not isinstance(reset_all_users, bool):
            return jsonify({"error": "El parámetro 'reset_all_users' debe ser un booleano"}), 400
        
        if not isinstance(include_2_uses, bool):
            return jsonify({"error": "El parámetro 'include_2_uses' debe ser un booleano"}), 400
        
        # Obtener estadísticas antes del reseteo
        if reset_all_users:
            stats_before = {
                "completed_1_use": Email.query.filter(
                    Email.usage_count == 1,
                    Email.status == 'completed'
                ).count(),
                "completed_2_uses": Email.query.filter(
                    Email.usage_count == 2,
                    Email.status == 'completed'
                ).count() if include_2_uses else 0
            }
        else:
            stats_before = {
                "completed_1_use": Email.query.filter(
                    Email.user_id == target_user_id,
                    Email.usage_count == 1,
                    Email.status == 'completed'
                ).count(),
                "completed_2_uses": Email.query.filter(
                    Email.user_id == target_user_id,
                    Email.usage_count == 2,
                    Email.status == 'completed'
                ).count() if include_2_uses else 0
            }
        
        # Construir consulta base: emails con status = 'completed'
        # Por defecto: solo emails con usage_count = 1
        # Si include_2_uses = True: también emails con usage_count = 2 (para usuario 3)
        if reset_all_users:
            if include_2_uses:
                # Resetear para todos los usuarios: emails con 1 o 2 usos completados
                emails_to_reset = Email.query.filter(
                    Email.status == 'completed',
                    Email.usage_count.in_([1, 2])
                ).all()
            else:
                # Resetear para todos los usuarios: solo emails con 1 uso completado
                emails_to_reset = Email.query.filter(
                    Email.usage_count == 1,
                    Email.status == 'completed'
                ).all()
        else:
            if include_2_uses:
                # Resetear solo para el usuario especificado: emails con 1 o 2 usos completados
                emails_to_reset = Email.query.filter(
                    Email.user_id == target_user_id,
                    Email.status == 'completed',
                    Email.usage_count.in_([1, 2])
                ).all()
            else:
                # Resetear solo para el usuario especificado: solo emails con 1 uso completado
                emails_to_reset = Email.query.filter(
                    Email.user_id == target_user_id,
                    Email.usage_count == 1,
                    Email.status == 'completed'
                ).all()
        
        if not emails_to_reset:
            message = f"No hay emails completados para resetear"
            if include_2_uses:
                message += " (con 1 o 2 usos)"
            else:
                message += " (con 1 uso)"
            if not reset_all_users:
                message += f" para el usuario {target_user_id}"
            return jsonify({
                "message": message,
                "target_user_id": target_user_id if not reset_all_users else "todos",
                "reset_all_users": reset_all_users,
                "include_2_uses": include_2_uses,
                "reset_count": 0,
                "stats_before": stats_before
            }), 200
        
        # Agrupar por usuario y por usage_count para estadísticas
        emails_by_user = {}
        emails_by_usage = {1: [], 2: []}
        
        for email in emails_to_reset:
            # Agrupar por usuario
            if email.user_id not in emails_by_user:
                emails_by_user[email.user_id] = []
            emails_by_user[email.user_id].append(email)
            
            # Agrupar por usage_count
            if email.usage_count in [1, 2]:
                emails_by_usage[email.usage_count].append(email)
        
        # Resetear emails: usage_count = 0, status = 'active'
        reset_count = 0
        reset_emails_info = []
        
        for email in emails_to_reset:
            old_usage = email.usage_count
            email.usage_count = 0
            email.status = 'active'
            reset_emails_info.append({
                "id": email.id,
                "email": email.email,
                "user_id": email.user_id,
                "old_usage_count": old_usage,
                "old_status": "completed",
                "new_usage_count": 0,
                "new_status": "active"
            })
            reset_count += 1
        
        db.session.commit()
        
        # Obtener estadísticas después del reseteo
        if reset_all_users:
            stats_after = {
                "completed_1_use": Email.query.filter(
                    Email.usage_count == 1,
                    Email.status == 'completed'
                ).count(),
                "completed_2_uses": Email.query.filter(
                    Email.usage_count == 2,
                    Email.status == 'completed'
                ).count() if include_2_uses else stats_before.get("completed_2_uses", 0)
            }
        else:
            stats_after = {
                "completed_1_use": Email.query.filter(
                    Email.user_id == target_user_id,
                    Email.usage_count == 1,
                    Email.status == 'completed'
                ).count(),
                "completed_2_uses": Email.query.filter(
                    Email.user_id == target_user_id,
                    Email.usage_count == 2,
                    Email.status == 'completed'
                ).count() if include_2_uses else stats_before.get("completed_2_uses", 0)
            }
        
        # Preparar estadísticas por usuario
        stats_by_user = {}
        for user_id, user_emails in emails_by_user.items():
            stats_by_user[user_id] = len(user_emails)
        
        # Preparar estadísticas por usage_count
        stats_by_usage = {
            "reset_from_1_use": len(emails_by_usage[1]),
            "reset_from_2_uses": len(emails_by_usage[2]) if include_2_uses else 0
        }
        
        return jsonify({
            "message": f"Reseteo completado exitosamente",
            "target_user_id": target_user_id if not reset_all_users else "todos",
            "reset_all_users": reset_all_users,
            "include_2_uses": include_2_uses,
            "reset_count": reset_count,
            "stats_by_user": stats_by_user,
            "stats_by_usage": stats_by_usage,
            "stats_before": stats_before,
            "stats_after": stats_after,
            "emails_reset": reset_emails_info[:50],  # Mostrar solo los primeros 50
            "total_emails_reset": len(reset_emails_info),
            "note": f"Emails con status = 'completed' ahora tienen usage_count = 0 y status = 'active' (disponibles para usar). Reseteados: {stats_by_usage['reset_from_1_use']} con 1 uso" + (f", {stats_by_usage['reset_from_2_uses']} con 2 usos" if include_2_uses and stats_by_usage['reset_from_2_uses'] > 0 else "")
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error durante el reseteo: {str(e)}"}), 500
