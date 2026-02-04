from flask import Blueprint, request, jsonify
from app.database import db
from app.models.proxy import Proxy, ProxyKind
from app.models.user import User
from app.utils.auth import token_required, session_or_token_required
from app.services.encrypt import encrypt_service
from app.services.proxy_providers import DataimpulseProvider


proxies_bp = Blueprint('proxies', __name__, url_prefix='/api/proxies')


#! ENDPOINT PARA OBTENER PROXIES POR USUARIO
@proxies_bp.route('/user/<int:user_id>', methods=['GET'])
@token_required
def get_user_proxies(user_id):
    try:
        # Verificar permisos: usuario actual o admin (si hubiera lógica de admin)
        # Por ahora permitimos si el token es válido
        
        proxies = Proxy.query.filter_by(user_id=user_id).all()
        return jsonify({
            "message": "Proxies obtenidos exitosamente",
            "proxies": [p.to_dict() for p in proxies]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


#! ENDPOINT PARA CREAR UN PROXY
@proxies_bp.route('/', methods=['POST'])
@session_or_token_required
def create_proxy():
    try:
        data = request.json
        current_user = request.current_user

        name = data.get('name')
        host = data.get('host')
        port = data.get('port')
        username = data.get('username')
        password = data.get('password')
        kind_str = data.get('kind', 'unknown')

        if not all([name, host, port]):
            return jsonify({"error": "Faltan datos requeridos (name, host, port)"}), 400

        try:
            kind = ProxyKind(kind_str)
        except ValueError:
            return jsonify({"error": "Tipo de proxy inválido"}), 400

        encrypted_password = None
        if password:
            encrypted_password = encrypt_service.encrypt(password)

        new_proxy = Proxy(
            user_id=current_user.id,
            name=name,
            host=host,
            port=port,
            username=username,
            password=encrypted_password,
            kind=kind,
            is_active=data.get('is_active', True)
        )

        db.session.add(new_proxy)
        db.session.commit()

        return jsonify({
            "message": "Proxy creado exitosamente",
            "proxy": new_proxy.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


#! ENDPOINT PARA OBTENER ESTADISTICAS
@proxies_bp.route('/<int:proxy_id>/stats', methods=['GET'])
@session_or_token_required
def get_proxy_stats(proxy_id):
    try:
        current_user = request.current_user
        proxy = Proxy.query.filter_by(id=proxy_id).first()

        if not proxy:
            return jsonify({"error": "Proxy no encontrado"}), 404

        if proxy.user_id != current_user.id:
            return jsonify({"error": "No autorizado"}), 403

        if proxy.kind != ProxyKind.DATAIMPULSE:
            return jsonify({"error": "Este tipo de proxy no soporta estadísticas"}), 400

        # Obtener credenciales
        decrypted_password = None
        if proxy.password:
            decrypted_password = encrypt_service.decrypt(proxy.password)

        if not proxy.username or not decrypted_password:
             return jsonify({"error": "Credenciales incompletas para obtener estadísticas"}), 400

        provider = DataimpulseProvider()
        stats = provider.get_status(proxy.username, decrypted_password)

        return jsonify({
            "message": "Estadísticas obtenidas",
            "stats": stats.__dict__
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


#! ENDPOINT PARA OBTENER UN PROXY POR ID
@proxies_bp.route('/<int:proxy_id>', methods=['GET'])
@session_or_token_required
def get_proxy(proxy_id):
    try:
        current_user = request.current_user
        proxy = Proxy.query.filter_by(id=proxy_id, user_id=current_user.id).first()

        if not proxy:
            return jsonify({"error": "Proxy no encontrado"}), 404

        return jsonify({
            "message": "Proxy obtenido exitosamente",
            "proxy": proxy.to_dict()
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


#! ENDPOINT PARA ACTUALIZAR UN PROXY
@proxies_bp.route('/<int:proxy_id>', methods=['PUT'])
@session_or_token_required
def update_proxy(proxy_id):
    try:
        current_user = request.current_user
        proxy = Proxy.query.filter_by(id=proxy_id, user_id=current_user.id).first()

        if not proxy:
            return jsonify({"error": "Proxy no encontrado"}), 404

        data = request.json

        # Actualizar campos permitidos
        if 'name' in data:
            proxy.name = data['name']
        if 'host' in data:
            proxy.host = data['host']
        if 'port' in data:
            proxy.port = data['port']
        if 'username' in data:
            proxy.username = data['username']
        if 'password' in data and data['password']:
            # Solo actualizar password si se proporciona uno nuevo
            proxy.password = encrypt_service.encrypt(data['password'])
        if 'kind' in data:
            try:
                proxy.kind = ProxyKind(data['kind'])
            except ValueError:
                return jsonify({"error": "Tipo de proxy inválido"}), 400
        if 'is_active' in data:
            proxy.is_active = data['is_active']

        db.session.commit()

        return jsonify({
            "message": "Proxy actualizado exitosamente",
            "proxy": proxy.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
