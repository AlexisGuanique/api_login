import jwt
import os
import re

from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from app.models.email import Email
from app.models.user import User
from app.database import db
from app.utils.auth import token_required

emails_bp = Blueprint('emails', __name__, url_prefix='/api/emails')

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
    
    # Verificar dominios duplicados en la lista enviada
    if len(emails_list) != len(set(emails_list)):
        return jsonify({"error": "No se permiten dominios duplicados en la misma petición"}), 400
    
    # Verificar si algún email ya existe para este usuario
    existing_emails = Email.query.filter(
        Email.email.in_(emails_list),
        Email.user_id == user_id
    ).all()
    
    # Crear diccionario para acceso rápido por email
    existing_emails_dict = {email.email: email for email in existing_emails}
    
    # Separar emails en categorías
    new_emails_list = []
    available_emails_list = []  # Emails con usage_count = 0 y status = 'active'
    recycled_emails_list = []   # Emails que se van a reciclar (usage_count = 1)
    completed_emails_list = []  # Emails completados que se van a reiniciar (status = 'completed')
    
    for email_address in emails_list:
        if email_address in existing_emails_dict:
            existing_email = existing_emails_dict[email_address]
            if existing_email.status == 'completed':
                # Email completado - reiniciar completamente
                completed_emails_list.append(email_address)
            elif existing_email.usage_count == 0 and existing_email.status == 'active':
                available_emails_list.append(email_address)
            elif existing_email.usage_count == 1 and existing_email.status == 'active':
                recycled_emails_list.append(email_address)
            elif existing_email.usage_count == 2 and existing_email.status == 'active':
                recycled_emails_list.append(email_address)
        else:
            new_emails_list.append(email_address)
    
    # Crear nuevos emails solo para los que no existen
    new_emails = []
    recycled_emails = []
    restarted_emails = []
    try:
        # Crear emails nuevos
        for email_address in new_emails_list:
            new_email = Email(
                email=email_address,
                user_id=user_id,
                usage_count=0,
                status='active'
            )
            new_emails.append(new_email)
            db.session.add(new_email)
        
        # Reciclar emails existentes activos
        for email_address in recycled_emails_list:
            existing_email = existing_emails_dict[email_address]
            if existing_email.usage_count == 1:
                # Reiniciar de 1 a 0 (disponible para usar)
                existing_email.usage_count = 0
                recycled_emails.append(email_address)
            elif existing_email.usage_count == 2:
                # Reiniciar de 2 a 1 (un uso disponible)
                existing_email.usage_count = 1
                recycled_emails.append(email_address)
        
        # Reiniciar emails completados
        for email_address in completed_emails_list:
            existing_email = existing_emails_dict[email_address]
            # Reiniciar desde completado: status = 'active', usage_count = 1 (disponible para un uso más)
            existing_email.status = 'active'
            existing_email.usage_count = 1
            restarted_emails.append(email_address)
        
        db.session.commit()
        
        # Preparar mensaje según el resultado
        total_processed = len(new_emails) + len(recycled_emails) + len(restarted_emails) + len(available_emails_list)
        
        message_parts = []
        if len(new_emails) > 0:
            message_parts.append(f"{len(new_emails)} nuevo(s)")
        if len(recycled_emails) > 0:
            message_parts.append(f"{len(recycled_emails)} reciclado(s)")
        if len(restarted_emails) > 0:
            message_parts.append(f"{len(restarted_emails)} reiniciado(s) desde completados (1 uso disponible)")
        if len(available_emails_list) > 0:
            message_parts.append(f"{len(available_emails_list)} ya disponible(s)")
        
        if len(message_parts) > 1:
            message = f"Procesamiento completado: {', '.join(message_parts)}"
        elif len(message_parts) == 1:
            message = f"Procesamiento completado: {message_parts[0]}"
        else:
            message = "No se procesaron emails"
        
        response_data = {
            "message": message,
            "saved_count": len(new_emails),
            "recycled_count": len(recycled_emails),
            "restarted_count": len(restarted_emails),
            "available_count": len(available_emails_list),
            "invalid_format_count": len(invalid_emails),
            "total_processed": len(emails_list)
        }
        
        # Agregar emails reciclados si hay alguno
        if recycled_emails:
            response_data["recycled_emails"] = recycled_emails
        
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
        status_code = 201 if (new_emails_list or recycled_emails or restarted_emails) else 200
        
        return jsonify(response_data), status_code
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al guardar los emails: {str(e)}"}), 500


#! ENDPOINT PARA OBTENER EMAILS DISPONIBLES DE UN USUARIO (usage_count = 0 y usage_count = 1)
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
            token_data = jwt.decode(access_token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            token_username = token_data.get('username')
            
            # Buscar el usuario por username para obtener su ID
            user = User.query.filter_by(username=token_username).first()
            if not user:
                return jsonify({"error": "Usuario no encontrado"}), 401
            
            # Verificar que el token pertenece al usuario solicitado
            if user.id != user_id:
                return jsonify({"error": "Token no válido para este usuario"}), 401
                
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expirado"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token inválido"}), 401
        
        # Obtener emails disponibles (usage_count = 0 o usage_count = 1, y status = 'active')
        available_emails = Email.query.filter(
            Email.user_id == user_id,
            Email.status == 'active',
            Email.usage_count.in_([0, 1])
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
            token_data = jwt.decode(access_token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            token_username = token_data.get('username')
            
            # Buscar el usuario por username para obtener su ID
            user = User.query.filter_by(username=token_username).first()
            if not user:
                return jsonify({"error": "Usuario no encontrado"}), 401
            
            # Verificar que el token pertenece al usuario solicitado
            if user.id != user_id:
                return jsonify({"error": "Token no válido para este usuario"}), 401
                
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expirado"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token inválido"}), 401
        
        # Obtener parámetros de limpieza
        days_old = data.get('days_old', 7)  # Por defecto, eliminar emails completados de hace 7 días
        dry_run = data.get('dry_run', False)  # Por defecto, hacer limpieza real
        
        if not isinstance(days_old, int) or days_old < 1:
            return jsonify({"error": "days_old debe ser un número entero positivo"}), 400
        
        # Calcular fecha límite
        from datetime import datetime, timedelta
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
        email_ids = [email.id for email in old_completed_emails]
        deleted_count = Email.query.filter(Email.id.in_(email_ids)).delete(synchronize_session=False)
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
            token_data = jwt.decode(access_token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            token_username = token_data.get('username')
            
            # Buscar el usuario por username para obtener su ID
            user = User.query.filter_by(username=token_username).first()
            if not user:
                return jsonify({"error": "Usuario no encontrado"}), 401
            
            # Verificar que el token pertenece al usuario solicitado
            if user.id != user_id:
                return jsonify({"error": "Token no válido para este usuario"}), 401
                
        except jwt.ExpiredSignatureError:
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
            token_data = jwt.decode(access_token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            token_username = token_data.get('username')
            
            # Buscar el usuario por username para obtener su ID
            user = User.query.filter_by(username=token_username).first()
            if not user:
                return jsonify({"error": "Usuario no encontrado"}), 401
            
            # Verificar que el token pertenece al usuario solicitado
            if user.id != user_id:
                return jsonify({"error": "Token no válido para este usuario"}), 401
                
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expirado"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token inválido"}), 401
        
        # Obtener parámetros
        days_old = data.get('days_old', 7)  # Por defecto 7 días
        
        if not isinstance(days_old, int) or days_old < 1:
            return jsonify({"error": "days_old debe ser un número entero positivo"}), 400
        
        # Calcular fecha límite
        from datetime import datetime, timedelta
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
                "deleted_count": 0,
                "emails_before": {
                    "total": Email.query.filter_by(user_id=user_id).count(),
                    "completed": Email.query.filter_by(user_id=user_id, status='completed').count(),
                    "active": Email.query.filter_by(user_id=user_id, status='active').count()
                }
            }), 200
        
        # Eliminar emails completados antiguos
        email_ids = [email.id for email in old_completed_emails]
        deleted_count = Email.query.filter(Email.id.in_(email_ids)).delete(synchronize_session=False)
        db.session.commit()
        
        # Estadísticas después de la limpieza
        stats_after = {
            "total": Email.query.filter_by(user_id=user_id).count(),
            "completed": Email.query.filter_by(user_id=user_id, status='completed').count(),
            "active": Email.query.filter_by(user_id=user_id, status='active').count()
        }
        
        return jsonify({
            "message": f"Limpieza completada exitosamente",
            "user_id": user_id,
            "days_old": days_old,
            "cutoff_date": cutoff_date.isoformat(),
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
            token_data = jwt.decode(access_token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            token_username = token_data.get('username')
            
            # Buscar el usuario por username para obtener su ID
            user = User.query.filter_by(username=token_username).first()
            if not user:
                return jsonify({"error": "Usuario no encontrado"}), 401
            
            # Verificar que el token pertenece al usuario solicitado
            if user.id != user_id:
                return jsonify({"error": "Token no válido para este usuario"}), 401
                
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expirado"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token inválido"}), 401
        
        # Obtener parámetros
        days_old = data.get('days_old', 7)  # Por defecto 7 días
        
        if not isinstance(days_old, int) or days_old < 1:
            return jsonify({"error": "days_old debe ser un número entero positivo"}), 400
        
        # Calcular fecha límite
        from datetime import datetime, timedelta
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


#! ENDPOINT PARA OBTENER EMAILS USADOS DE UN USUARIO (usage_count > 0)
@emails_bp.route('/used/<int:user_id>', methods=['POST'])
@token_required
def get_used_emails(user_id):
    try:
        # Obtener emails usados (usage_count > 0 y status = 'active')
        used_emails = Email.query.filter(
            Email.user_id == user_id,
            Email.usage_count > 0,
            Email.status == 'active'
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
        # Contar emails del usuario por estado de uso y status
        total_count = db.session.query(Email).filter_by(user_id=user_id).count()
        available_count = db.session.query(Email).filter_by(user_id=user_id, usage_count=0, status='active').count()
        used_once_count = db.session.query(Email).filter_by(user_id=user_id, usage_count=1, status='active').count()
        used_twice_count = db.session.query(Email).filter_by(user_id=user_id, usage_count=2, status='active').count()
        completed_count = db.session.query(Email).filter_by(user_id=user_id, status='completed').count()
        
        return jsonify({
            "message": "Cantidad de emails obtenida exitosamente",
            "user_id": user_id,
            "total_count": total_count,
            "available_count": available_count,
            "used_once_count": used_once_count,
            "used_twice_count": used_twice_count,
            "completed_count": completed_count,
            "breakdown": {
                "disponibles": available_count,
                "usados_una_vez": used_once_count,
                "usados_dos_veces": used_twice_count,
                "completados": completed_count
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
        
        # Consulta optimizada: obtener emails activos disponibles (status = 'active' y usage_count < 2) ordenados por fecha de creación (FIFO)
        # with_for_update(skip_locked=True) previene condiciones de carrera
        emails = db.session.query(Email.id, Email.email, Email.created_at, Email.usage_count, Email.status).filter(
            Email.user_id == user_id,
            Email.status == 'active',
            Email.usage_count < 2
        ).order_by(Email.created_at.asc()).with_for_update(skip_locked=True).limit(count).all()
        
        if not emails:
            return jsonify({
                "message": "No hay emails disponibles",
                "emails": [],
                "count": 0,
                "requested_count": count
            }), 200
        
        # Crear lista de emails para la respuesta
        emails_data = []
        email_ids = []
        emails_to_complete = []
        
        for email in emails:
            email_data = {
                'id': email.id,
                'email': email.email,
                'created_at': email.created_at.isoformat() if email.created_at else None,
                'user_id': user_id,
                'usage_count': email.usage_count + 1,  # Mostrar el nuevo usage_count
                'status': 'completed' if email.usage_count == 1 else 'active'  # Mostrar el nuevo status
            }
            emails_data.append(email_data)
            email_ids.append(email.id)
            
            # Si ya se usó una vez, marcar para completar después del segundo uso
            if email.usage_count == 1:
                emails_to_complete.append(email.id)
        
        # Incrementar usage_count para todos los emails obtenidos
        db.session.query(Email).filter(Email.id.in_(email_ids)).update(
            {Email.usage_count: Email.usage_count + 1}, 
            synchronize_session=False
        )
        
        # Marcar como completados los emails que ya han sido usados dos veces
        if emails_to_complete:
            db.session.query(Email).filter(Email.id.in_(emails_to_complete)).update(
                {Email.status: 'completed'}, 
                synchronize_session=False
            )
        
        db.session.commit()
        
        # Mensaje según la cantidad procesada
        completed_count = len(emails_to_complete)
        active_count = len(emails_data) - completed_count
        
        if len(emails_data) == 1:
            if completed_count == 1:
                message = "Email obtenido y completado (segundo uso finalizado, disponible para reciclaje)"
            else:
                message = "Email obtenido (primer uso, disponible para reciclaje)"
        else:
            if completed_count > 0 and active_count > 0:
                message = f"{len(emails_data)} emails obtenidos: {completed_count} completados (segundo uso), {active_count} activos para reciclaje"
            elif completed_count > 0:
                message = f"{len(emails_data)} emails obtenidos y completados (segundo uso finalizado, disponibles para reciclaje)"
            else:
                message = f"{len(emails_data)} emails obtenidos (primer uso, disponibles para reciclaje)"
        
        response_data = {
            "message": message,
            "emails": emails_data,
            "count": len(emails_data),
            "requested_count": count,
            "completed_count": completed_count,
            "active_count": active_count
        }
        
        # Si se pidieron más emails de los disponibles, agregar información
        if len(emails_data) < count:
            response_data["note"] = f"Solo se encontraron {len(emails_data)} emails de los {count} solicitados"
        
        return jsonify(response_data), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al obtener los emails: {str(e)}"}), 500
