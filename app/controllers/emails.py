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
            "user_username": email.user.username if email.user else None
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
            "user_id": email.user_id
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
        return jsonify({"error": "Email(s) requerido(s)"}), 400
    
    # Convertir a lista si es un string único
    if isinstance(emails_data, str):
        emails_list = [emails_data]
    elif isinstance(emails_data, list):
        emails_list = emails_data
    else:
        return jsonify({"error": "Formato inválido. Debe ser string o lista de strings"}), 400
    
    # Validar que todos los elementos sean strings
    if not all(isinstance(email, str) for email in emails_list):
        return jsonify({"error": "Todos los emails deben ser strings"}), 400
    
    # Validar formato de cada email (pero permitir guardar todos)
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    invalid_emails = []
    valid_emails = []
    
    for email in emails_list:
        if not re.match(email_pattern, email):
            invalid_emails.append(email)
        else:
            valid_emails.append(email)
    
    # Verificar emails duplicados en la lista enviada
    if len(emails_list) != len(set(emails_list)):
        return jsonify({"error": "No se permiten emails duplicados en la misma petición"}), 400
    
    # Verificar si algún email ya existe para este usuario
    existing_emails = Email.query.filter(
        Email.email.in_(emails_list),
        Email.user_id == user_id
    ).all()
    
    # Separar emails existentes de los nuevos
    existing_emails_list = [email.email for email in existing_emails]
    new_emails_list = [email for email in emails_list if email not in existing_emails_list]
    
    # Crear nuevos emails solo para los que no existen
    new_emails = []
    try:
        for email_address in new_emails_list:
            new_email = Email(
                email=email_address,
                user_id=user_id
            )
            new_emails.append(new_email)
            db.session.add(new_email)
        
        db.session.commit()
        
        # Preparar mensaje según el resultado
        if existing_emails_list and new_emails_list:
            message = f"Procesamiento completado: {len(new_emails)} email(s) guardado(s), {len(existing_emails_list)} ya existían"
        elif existing_emails_list and not new_emails_list:
            message = f"Todos los emails ya existen en la base de datos ({len(existing_emails_list)} duplicados)"
        else:
            message = f"{len(new_emails)} email(s) guardado(s) exitosamente"
            if len(new_emails) == 1:
                message = "Email guardado exitosamente"
        
        response_data = {
            "message": message,
            "saved_count": len(new_emails),
            "duplicate_count": len(existing_emails_list),
            "invalid_format_count": len(invalid_emails),
            "total_processed": len(emails_list)
        }
        
        # Agregar emails duplicados si hay alguno
        if existing_emails_list:
            response_data["duplicate_emails"] = existing_emails_list
        
        # Agregar emails con formato inválido si hay alguno
        if invalid_emails:
            response_data["invalid_format_emails"] = invalid_emails
        
        # Código de estado según el resultado
        status_code = 201 if new_emails_list else 200
        
        return jsonify(response_data), status_code
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al guardar los emails: {str(e)}"}), 500


#! ENDPOINT PARA OBTENER CANTIDAD DE EMAILS DE UN USUARIO
@emails_bp.route('/count/<int:user_id>', methods=['POST'])
@token_required
def get_email_count(user_id):
    try:
        # Contar emails del usuario usando consulta optimizada
        email_count = db.session.query(Email).filter_by(user_id=user_id).count()
        
        return jsonify({
            "message": "Cantidad de emails obtenida exitosamente",
            "user_id": user_id,
            "email_count": email_count
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
        
        # Limitar la cantidad máxima para evitar sobrecarga
        if count > 100:
            return jsonify({"error": "No se pueden procesar más de 100 emails a la vez"}), 400
        
        # Consulta optimizada: obtener emails ordenados por fecha de creación (FIFO)
        # with_for_update(skip_locked=True) previene condiciones de carrera
        emails = db.session.query(Email.id, Email.email, Email.created_at).filter_by(
            user_id=user_id
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
        
        for email in emails:
            email_data = {
                'id': email.id,
                'email': email.email,
                'created_at': email.created_at.isoformat() if email.created_at else None,
                'user_id': user_id
            }
            emails_data.append(email_data)
            email_ids.append(email.id)
        
        # Eliminar emails procesados usando solo los IDs para mayor eficiencia
        db.session.query(Email).filter(Email.id.in_(email_ids)).delete(synchronize_session=False)
        db.session.commit()
        
        # Mensaje según la cantidad procesada
        if len(emails_data) == 1:
            message = "Email obtenido y eliminado exitosamente"
        else:
            message = f"{len(emails_data)} emails obtenidos y eliminados exitosamente"
        
        response_data = {
            "message": message,
            "emails": emails_data,
            "count": len(emails_data),
            "requested_count": count
        }
        
        # Si se pidieron más emails de los disponibles, agregar información
        if len(emails_data) < count:
            response_data["note"] = f"Solo se encontraron {len(emails_data)} emails de los {count} solicitados"
        
        return jsonify(response_data), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al obtener los emails: {str(e)}"}), 500
