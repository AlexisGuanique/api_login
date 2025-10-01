from functools import wraps
from flask import request, jsonify, current_app
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
            # Decodificar el token para verificar su estructura
            payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
            
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
            
            # Verificar si el token ha expirado
            if user.token_expiration and datetime.utcnow() > user.token_expiration:
                return jsonify({"error": "El token ha expirado"}), 401
                
            # Agregar el usuario autenticado al contexto de la función
            request.current_user = user
            
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "El token ha expirado"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token inválido"}), 401
        except Exception as e:
            return jsonify({"error": f"Error de autenticación: {str(e)}"}), 500

        return f(*args, **kwargs)

    return decorated_function
