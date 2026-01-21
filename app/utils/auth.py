from functools import wraps
from flask import request, jsonify, current_app, session
import jwt
from datetime import datetime
from app.models.user import User

def token_required(f):
    """
    Decorador para autenticar endpoints usando access_token del body de la petición.
    Verifica que el token sea válido y no haya expirado.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Obtener el token del body de la petición
        data = request.get_json()
        if not data:
            return jsonify({"error": "Body de la petición requerido"}), 400
            
        token = data.get("access_token")

        if not token:
            return jsonify({"error": "access_token no proporcionado en el body"}), 401

        try:
            # Decodificar el token sin verificar exp automáticamente
            # Usamos verify_exp=False para evitar que PyJWT falle si el exp del JWT ha expirado
            # La verificación real se hace contra token_expiration de la base de datos
            payload = jwt.decode(
                token, 
                current_app.config["SECRET_KEY"], 
                algorithms=["HS256"],
                options={"verify_exp": False}
            )
            
            # Obtener el username del payload
            username = payload.get("username")
            if not username:
                return jsonify({"error": "Token inválido: username no encontrado"}), 401
            
            # Buscar el usuario en la base de datos
            user = User.query.filter_by(username=username).first()
            if not user:
                return jsonify({"error": "Usuario no encontrado"}), 401
            
            # Verificar que el token coincida con el almacenado en la base de datos
            if user.access_token != token:
                return jsonify({"error": "Token no coincide con el almacenado"}), 401
            
            # Verificar si el token ha expirado según la base de datos (fuente de verdad)
            if user.token_expiration and datetime.utcnow() > user.token_expiration:
                return jsonify({"error": "El token ha expirado"}), 401
                
            # Agregar el usuario autenticado al contexto de la función
            request.current_user = user
            
        except jwt.InvalidTokenError as e:
            # Capturar errores de token inválido (firma incorrecta, formato incorrecto, etc.)
            # pero no ExpiredSignatureError ya que desactivamos verify_exp
            return jsonify({"error": f"Token inválido: {str(e)}"}), 401
        except Exception as e:
            return jsonify({"error": f"Error de autenticación: {str(e)}"}), 500

        return f(*args, **kwargs)

    return decorated_function


def session_or_token_required(f):
    """
    Decorador para autenticar endpoints usando sesión (para web) o access_token del body (para API).
    Primero intenta usar la sesión, si no está disponible, usa el token del body.
    Verifica que el token sea válido y no haya expirado.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        user = None
        
        # Primero intentar obtener el token de la sesión (para web)
        if session.get("user_id") and session.get("access_token"):
            token = session.get("access_token")
            user_id = session.get("user_id")
            user = User.query.filter_by(id=user_id).first()
            
            # Verificar que el token de la sesión coincida con el del usuario
            if user and user.access_token == token:
                # Verificar si el token ha expirado
                if user.token_expiration and datetime.utcnow() > user.token_expiration:
                    return jsonify({"error": "El token ha expirado"}), 401
                request.current_user = user
                return f(*args, **kwargs)
        
        # Si no hay sesión válida, intentar obtener el token del body (para API)
        data = request.get_json() or {}
        token = data.get("access_token")
        
        if not token:
            return jsonify({"error": "No autenticado. Inicia sesión o proporciona access_token"}), 401

        try:
            # Decodificar el token sin verificar exp automáticamente
            payload = jwt.decode(
                token, 
                current_app.config["SECRET_KEY"], 
                algorithms=["HS256"],
                options={"verify_exp": False}
            )
            
            # Obtener el username del payload
            username = payload.get("username")
            if not username:
                return jsonify({"error": "Token inválido: username no encontrado"}), 401
            
            # Buscar el usuario en la base de datos
            user = User.query.filter_by(username=username).first()
            if not user:
                return jsonify({"error": "Usuario no encontrado"}), 401
            
            # Verificar que el token coincida con el almacenado en la base de datos
            if user.access_token != token:
                return jsonify({"error": "Token no coincide con el almacenado"}), 401
            
            # Verificar si el token ha expirado según la base de datos
            if user.token_expiration and datetime.utcnow() > user.token_expiration:
                return jsonify({"error": "El token ha expirado"}), 401
                
            # Agregar el usuario autenticado al contexto de la función
            request.current_user = user
            
        except jwt.InvalidTokenError as e:
            return jsonify({"error": f"Token inválido: {str(e)}"}), 401
        except Exception as e:
            return jsonify({"error": f"Error de autenticación: {str(e)}"}), 500

        return f(*args, **kwargs)

    return decorated_function
