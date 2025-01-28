import jwt
import os

from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from flask import Blueprint, request, jsonify, current_app
from app.models.user import User
from app.database import db

load_dotenv()

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

#! ENDPOINT PARA OBTENER LOS USUARIOS
@auth_bp.route('/users', methods=['GET'])
def get_all_users():
    admin_key = request.headers.get('Admin-Key')

    # Verificar si el Admin-Key es válido
    if admin_key != os.getenv('ADMIN_KEY'):
        return jsonify({"error": "Acceso no autorizado"}), 403

    # Obtener todos los usuarios de la base de datos
    users = User.query.all()

    # Formatear la lista de usuarios para la respuesta
    users_list = [
        {
            "id": user.id,
            "username": user.username,
            "name": user.name,  # Nuevo campo
            "lastname": user.lastname,  # Nuevo campo
            "password": user.password,  # Contraseña encriptada
            "token_expiration": user.token_expiration.strftime('%Y-%m-%d %H:%M:%S') if user.token_expiration else None,
            "access_token": user.access_token
        }
        for user in users
    ]

    # Respuesta final
    return jsonify({
        "message": "Usuarios obtenidos exitosamente",
        "users": users_list
    }), 200



#! ENDPOINT PARA OBTENER UN USUARIO
@auth_bp.route('/user/<int:user_id>', methods=['GET'])
def get_user(user_id):
    admin_key = request.headers.get('Admin-Key')

    # Verificar si se proporciona el Admin-Key y si es válido
    if admin_key != os.getenv('ADMIN_KEY'):
        return jsonify({"error": "Acceso no autorizado"}), 403

    # Buscar el usuario por id
    user = User.query.filter_by(id=user_id).first()

    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    # Formatear la información del usuario
    user_data = {
        "id": user.id,
        "username": user.username,
        "name": user.name,  # Nuevo campo
        "lastname": user.lastname,  # Nuevo campo
        "password": user.password,
        "token_expiration": user.token_expiration.strftime('%Y-%m-%d %H:%M:%S') if user.token_expiration else None,
        "access_token": user.access_token
    }

    return jsonify({
        "message": "Usuario obtenido exitosamente",
        "user": user_data
    }), 200



#! ENDPOINT PARA MODIFICAR UN USUARIO
@auth_bp.route('/user/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    admin_key = request.headers.get('Admin-Key')

    # Verificar si el Admin-Key es válido
    if admin_key != os.getenv('ADMIN_KEY'):
        return jsonify({"error": "Acceso no autorizado"}), 403

    # Obtener datos del body
    data = request.json

    # Verificar si hay elementos no permitidos en el body
    allowed_fields = {'username', 'password', 'name', 'lastname'}
    extra_fields = set(data.keys()) - allowed_fields

    if extra_fields:
        return jsonify({
            "error": "Uno o más elementos no se pueden modificar",
            "extra_fields": list(extra_fields)  # Mostrar los campos no permitidos
        }), 400

    # Buscar el usuario en la base de datos
    user = User.query.filter_by(id=user_id).first()

    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    # Actualizar datos del usuario
    username = data.get('username')
    password = data.get('password')
    name = data.get('name')  # Nuevo campo
    lastname = data.get('lastname')  # Nuevo campo

    if username:
        user.username = username
    if password:
        user.password = generate_password_hash(password)
    if name:
        user.name = name
    if lastname:
        user.lastname = lastname

    # Guardar cambios en la base de datos
    db.session.commit()

    # Formatear la respuesta
    updated_user = {
        "id": user.id,
        "username": user.username,
        "name": user.name,  # Nuevo campo
        "lastname": user.lastname,  # Nuevo campo
        "password": user.password,
        "token_expiration": user.token_expiration.strftime('%Y-%m-%d %H:%M:%S') if user.token_expiration else None,
        "access_token": user.access_token  # Se mantiene el token original
    }

    return jsonify({
        "message": "Usuario actualizado exitosamente",
        "user": updated_user
    }), 200


#! ENDPOONT REGISTER
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.json
    admin_key = request.headers.get('Admin-Key')

    if admin_key != os.getenv('ADMIN_KEY'):
        return jsonify({"error": "Acceso no autorizado"}), 403

    username = data.get('username')
    password = data.get('password')
    name = data.get('name')  
    lastname = data.get('lastname') 

    if not username or not password:
        return jsonify({"error": "Usuario y contraseña son requeridos"}), 400

    # Verificar si el usuario ya existe
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({"error": "El usuario ya existe"}), 409

    # Crear un nuevo usuario
    hashed_password = generate_password_hash(password)
    expiration = datetime.utcnow() + timedelta(days=30)
    access_token = jwt.encode(
        {"username": username, "exp": expiration},
        str(current_app.config["SECRET_KEY"]),
        algorithm="HS256"
    )
    new_user = User(
        username=username,
        password=hashed_password,
        name=name, 
        lastname=lastname, 
        access_token=access_token,
        token_expiration=expiration
    )
    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        "message": "Usuario registrado exitosamente",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "name": new_user.name,  # Nuevo campo
            "lastname": new_user.lastname,  # Nuevo campo
            "access_token": new_user.access_token,
            "token_expiration": new_user.token_expiration.strftime('%Y-%m-%d %H:%M:%S')
        }
    }), 201


#! ENDPOONT DELETE USER
@auth_bp.route('/user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    admin_key = request.headers.get('Admin-Key')

    # Verificar si el Admin-Key es válido
    if admin_key != os.getenv('ADMIN_KEY'):
        return jsonify({"error": "Acceso no autorizado"}), 403

    # Buscar el usuario en la base de datos
    user = User.query.filter_by(id=user_id).first()

    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    # Eliminar el usuario
    db.session.delete(user)
    db.session.commit()

    return jsonify({
        "message": "Usuario eliminado exitosamente",
        "user_id": user_id
    }), 200



#! ENDPOINT PARA LOGIN
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Usuario y contraseña son requeridos"}), 400

    # Buscar usuario en la base de datos
    user = User.query.filter_by(username=username).first()

    if user:
        # Verificar el hash o la contraseña sin hash
        if check_password_hash(user.password, password) or user.password == password:
            # Verificar si el token ha expirado
            if user.token_expiration and user.token_expiration > datetime.utcnow():
                return jsonify({
                    "message": "Login exitoso",
                    "id": user.id,
                    "access_token": user.access_token,
                    "expires_in": user.token_expiration.strftime('%Y-%m-%d %H:%M:%S'),
                    "name": user.name,
                    "lastname": user.lastname
                }), 200
            else:
                return jsonify({"error": "El token ha expirado, por favor registre nuevamente"}), 401

    return jsonify({"error": "Credenciales incorrectas"}), 401


#! ENDPOINT LOGOUT
@auth_bp.route('/logout', methods=['POST'])
def logout():
    return jsonify({"message": "Logout exitoso"}), 200



#! ENDPOINT VERIFY
@auth_bp.route('/verify-token/<int:user_id>', methods=['POST'])
def verify_token(user_id):
    data = request.json
    token = data.get("access_token")

    if not token:
        return jsonify({"error": "Token no proporcionado", "is_valid": False}), 400

    try:
        # Buscar el usuario por ID
        user = User.query.filter_by(id=user_id).first()

        if not user:
            return jsonify({"error": "Usuario no encontrado", "is_valid": False}), 404

        # Verificar si el token coincide con el almacenado en la base de datos
        if user.access_token != token:
            return jsonify({"error": "Token inválido", "is_valid": False}), 401

        # Verificar si el token ha expirado
        if user.token_expiration and datetime.utcnow() > user.token_expiration:
            return jsonify({
                "message": "El token ha expirado",
                "is_valid": False
            }), 200

        # Si todo es válido
        return jsonify({
            "message": "Token válido",
            "is_valid": True,
            "username": user.username,
            "name": user.name,
            "lastname": user.lastname
        }), 200

    except Exception as e:
        return jsonify({
            "message": f"Error inesperado: {str(e)}",
            "is_valid": False
        }), 500
