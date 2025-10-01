import os
import json

from datetime import datetime
from flask import Blueprint, request, jsonify
from app.models.account import Account
from app.models.user import User
from app.database import db
from app.utils.auth import token_required

accounts_bp = Blueprint('accounts', __name__, url_prefix='/api/accounts')

#! ENDPOINT PARA OBTENER TODAS LAS CUENTAS (Solo Admin)
@accounts_bp.route('/', methods=['GET'])
def get_all_accounts():
    admin_key = request.headers.get('Admin-Key')

    # Verificar si el Admin-Key es válido
    if admin_key != os.getenv('ADMIN_KEY'):
        return jsonify({"error": "Acceso no autorizado"}), 403

    # Obtener todas las cuentas de la base de datos
    accounts = Account.query.all()

    # Formatear la lista de cuentas para la respuesta
    accounts_list = [
        {
            "id": account.id,
            "user_agent": account.user_agent,
            "email": account.email,
            "password": account.password,
            "cookie": account.cookie,
            "created_at": account.created_at.isoformat() if account.created_at else None,
            "updated_at": account.updated_at.isoformat() if account.updated_at else None,
            "user_id": account.user_id,
            "user_username": account.user.username if account.user else None
        }
        for account in accounts
    ]

    # Respuesta final
    return jsonify({
        "message": "Cuentas obtenidas exitosamente",
        "accounts": accounts_list,
        "count": len(accounts_list)
    }), 200


#! ENDPOINT PARA OBTENER CUENTAS DE UN USUARIO ESPECÍFICO
@accounts_bp.route('/user/<int:user_id>', methods=['POST'])
@token_required
def get_user_accounts(user_id):
    # Obtener todas las cuentas del usuario
    user_accounts = Account.query.filter_by(user_id=user_id).all()

    # Formatear la lista de cuentas para la respuesta
    accounts_list = [
        {
            "id": account.id,
            "user_agent": account.user_agent,
            "email": account.email,
            "password": account.password,
            "cookie": account.cookie,
            "created_at": account.created_at.isoformat() if account.created_at else None,
            "updated_at": account.updated_at.isoformat() if account.updated_at else None,
            "user_id": account.user_id
        }
        for account in user_accounts
    ]

    return jsonify({
        "message": "Cuentas del usuario obtenidas exitosamente",
        "user_id": user_id,
        "accounts": accounts_list,
        "count": len(accounts_list)
    }), 200


#! ENDPOINT PARA GUARDAR CUENTAS (UNA O MÚLTIPLES)
@accounts_bp.route('/save/<int:user_id>', methods=['POST'])
@token_required
def save_accounts(user_id):
    # Obtener datos del body
    data = request.json
    
    # Obtener cuentas del body (puede ser objeto o lista)
    accounts_data = data.get('accounts') or data.get('account')
    
    if not accounts_data:
        return jsonify({"error": "Cuenta(s) requerida(s)"}), 400
    
    # Convertir a lista si es un objeto único
    if isinstance(accounts_data, dict):
        accounts_list = [accounts_data]
    elif isinstance(accounts_data, list):
        accounts_list = accounts_data
    else:
        return jsonify({"error": "Formato inválido. Debe ser objeto o lista de objetos"}), 400
    
    # Validar que todos los elementos sean diccionarios
    if not all(isinstance(account, dict) for account in accounts_list):
        return jsonify({"error": "Todas las cuentas deben ser objetos"}), 400
    
    # Validar campos requeridos para cada cuenta
    required_fields = ['user_agent', 'email', 'password', 'cookie']
    invalid_accounts = []
    valid_accounts = []
    
    for i, account in enumerate(accounts_list):
        missing_fields = [field for field in required_fields if field not in account or not account[field]]
        if missing_fields:
            invalid_accounts.append({
                "index": i,
                "account": account,
                "missing_fields": missing_fields
            })
        else:
            valid_accounts.append(account)
    
    if invalid_accounts:
        return jsonify({
            "error": "Algunas cuentas tienen campos faltantes",
            "invalid_accounts": invalid_accounts
        }), 400
    
    # Verificar cuentas duplicadas en la lista enviada (por email)
    emails_list = [account['email'] for account in valid_accounts]
    if len(emails_list) != len(set(emails_list)):
        return jsonify({"error": "No se permiten emails duplicados en la misma petición"}), 400
    
    # Verificar si alguna cuenta ya existe para este usuario
    existing_accounts = Account.query.filter(
        Account.email.in_(emails_list),
        Account.user_id == user_id
    ).all()
    
    # Separar cuentas existentes de las nuevas
    existing_emails_list = [account.email for account in existing_accounts]
    new_accounts_list = [account for account in valid_accounts if account['email'] not in existing_emails_list]
    
    # Crear nuevas cuentas solo para las que no existen
    new_accounts = []
    try:
        for account_data in new_accounts_list:
            # Procesar cookie - aceptar string, lista o diccionario
            cookie_value = account_data['cookie']
            try:
                if isinstance(cookie_value, str):
                    # Intentar parsear como JSON
                    try:
                        json.loads(cookie_value)  # Validar que sea JSON válido
                        # Si es válido, mantener como string
                        account_data['cookie'] = cookie_value
                    except json.JSONDecodeError:
                        # Si no es JSON válido, tratar como string literal
                        account_data['cookie'] = cookie_value
                elif isinstance(cookie_value, (list, dict)):
                    # Convertir a string JSON
                    account_data['cookie'] = json.dumps(cookie_value)
                else:
                    # Convertir cualquier otro tipo a string
                    account_data['cookie'] = str(cookie_value)
            except Exception as e:
                return jsonify({
                    "error": f"Error procesando cookie para la cuenta {account_data['email']}: {str(e)}"
                }), 400
            
            new_account = Account(
                user_agent=account_data['user_agent'],
                email=account_data['email'],
                password=account_data['password'],
                cookie=account_data['cookie'],
                user_id=user_id
            )
            new_accounts.append(new_account)
            db.session.add(new_account)
        
        db.session.commit()
        
        # Preparar mensaje según el resultado
        if existing_emails_list and new_accounts_list:
            message = f"Procesamiento completado: {len(new_accounts)} cuenta(s) guardada(s), {len(existing_emails_list)} ya existían"
        elif existing_emails_list and not new_accounts_list:
            message = f"Todas las cuentas ya existen en la base de datos ({len(existing_emails_list)} duplicadas)"
        else:
            message = f"{len(new_accounts)} cuenta(s) guardada(s) exitosamente"
            if len(new_accounts) == 1:
                message = "Cuenta guardada exitosamente"
        
        response_data = {
            "message": message,
            "saved_count": len(new_accounts),
            "duplicate_count": len(existing_emails_list),
            "total_processed": len(accounts_list)
        }
        
        # Agregar cuentas duplicadas si hay alguna
        if existing_emails_list:
            response_data["duplicate_emails"] = existing_emails_list
        
        # Código de estado según el resultado
        status_code = 201 if new_accounts_list else 200
        
        return jsonify(response_data), status_code
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al guardar las cuentas: {str(e)}"}), 500


#! ENDPOINT PARA OBTENER Y ELIMINAR ACCOUNTS (UNO O MÚLTIPLES)
@accounts_bp.route('/next/<int:user_id>', methods=['POST'])
@token_required
def get_next_accounts(user_id):
    try:
        # Obtener datos del body
        data = request.json or {}
        
        # Obtener cantidad de accounts a procesar (por defecto 1)
        count = data.get('count', 1)
        
        # Validar que count sea un número positivo
        if not isinstance(count, int) or count <= 0:
            return jsonify({"error": "El parámetro 'count' debe ser un número entero positivo"}), 400
        
        # Consulta optimizada: obtener accounts ordenados por fecha de creación (FIFO)
        # with_for_update(skip_locked=True) previene condiciones de carrera
        accounts = db.session.query(Account.id, Account.user_agent, Account.email, Account.password, Account.cookie, Account.created_at).filter_by(
            user_id=user_id
        ).order_by(Account.created_at.asc()).with_for_update(skip_locked=True).limit(count).all()
        
        if not accounts:
            return jsonify({
                "message": "No hay accounts disponibles",
                "accounts": [],
                "count": 0,
                "requested_count": count
            }), 200
        
        # Crear lista de accounts para la respuesta
        accounts_data = []
        account_ids = []
        
        for account in accounts:
            account_data = {
                'id': account.id,
                'user_agent': account.user_agent,
                'email': account.email,
                'password': account.password,
                'cookie': account.cookie,
                'created_at': account.created_at.isoformat() if account.created_at else None,
                'user_id': user_id
            }
            accounts_data.append(account_data)
            account_ids.append(account.id)
        
        # Eliminar accounts procesados usando solo los IDs para mayor eficiencia
        db.session.query(Account).filter(Account.id.in_(account_ids)).delete(synchronize_session=False)
        db.session.commit()
        
        # Mensaje según la cantidad procesada
        if len(accounts_data) == 1:
            message = "Account obtenido y eliminado exitosamente"
        else:
            message = f"{len(accounts_data)} accounts obtenidos y eliminados exitosamente"
        
        response_data = {
            "message": message,
            "accounts": accounts_data,
            "count": len(accounts_data),
            "requested_count": count
        }
        
        # Si se pidieron más accounts de los disponibles, agregar información
        if len(accounts_data) < count:
            response_data["note"] = f"Solo se encontraron {len(accounts_data)} accounts de los {count} solicitados"
        
        return jsonify(response_data), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al obtener los accounts: {str(e)}"}), 500


#! ENDPOINT PARA OBTENER CANTIDAD DE ACCOUNTS DE UN USUARIO
@accounts_bp.route('/count/<int:user_id>', methods=['POST'])
@token_required
def get_account_count(user_id):
    try:
        # Contar accounts del usuario usando consulta optimizada
        account_count = db.session.query(Account).filter_by(user_id=user_id).count()
        
        return jsonify({
            "message": "Cantidad de accounts obtenida exitosamente",
            "user_id": user_id,
            "account_count": account_count
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al obtener la cantidad de accounts: {str(e)}"}), 500

