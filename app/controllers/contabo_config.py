from flask import Blueprint, request, jsonify
from app.database import db
from app.models.contabo_config import ContaboConfig
from app.utils.auth import token_required, session_or_token_required
from app.services.contabo_encrypt import contabo_encrypt_service


contabo_config_bp = Blueprint('contabo_config', __name__, url_prefix='/api/contabo-config')


# @contabo_config_bp.route('/', methods=['GET'])
@session_or_token_required
def get_config():
    """Get Contabo config for current user (without sensitive fields)."""
    try:
        current_user = request.current_user
        config = ContaboConfig.query.filter_by(user_id=current_user.id).first()
        
        if not config:
            return jsonify({
                "message": "Configuración no encontrada",
                "config": None
            }), 200
        
        return jsonify({
            "message": "Configuración obtenida exitosamente",
            "config": config.to_dict(include_sensitive=False)
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# @contabo_config_bp.route('/', methods=['POST'])
@session_or_token_required
def save_config():
    """Create or update Contabo config for current user."""
    try:
        current_user = request.current_user
        data = request.json
        
        client_id = data.get('client_id')
        client_secret = data.get('client_secret')
        username = data.get('username')
        password = data.get('password')
        
        if not all([client_id, username]):
            return jsonify({"error": "client_id y username son requeridos"}), 400
        
        # Check if config exists
        config = ContaboConfig.query.filter_by(user_id=current_user.id).first()
        
        if config:
            # Update existing
            config.client_id = client_id
            config.username = username
            
            # Only update secrets if provided
            if client_secret:
                config.client_secret = contabo_encrypt_service.encrypt(client_secret)
            if password:
                config.password = contabo_encrypt_service.encrypt(password)
        else:
            # Create new - require all fields
            if not client_secret or not password:
                return jsonify({"error": "client_secret y password son requeridos para nueva configuración"}), 400
            
            config = ContaboConfig(
                user_id=current_user.id,
                client_id=client_id,
                client_secret=contabo_encrypt_service.encrypt(client_secret),
                username=username,
                password=contabo_encrypt_service.encrypt(password)
            )
            db.session.add(config)
        
        db.session.commit()
        
        return jsonify({
            "message": "Configuración guardada exitosamente",
            "config": config.to_dict(include_sensitive=False)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
