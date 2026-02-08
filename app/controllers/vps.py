from flask import Blueprint, request, jsonify
from app.database import db
from app.models.vps import VPS
from app.models.contabo_config import ContaboConfig
from app.utils.auth import token_required, session_or_token_required
from app.services.contabo import ContaboService, sync_instances_to_db
from app.services.contabo_encrypt import contabo_encrypt_service


vps_bp = Blueprint('vps', __name__, url_prefix='/api/vps')


# @vps_bp.route('/user/<int:user_id>', methods=['GET'])
@token_required
def get_user_vps(user_id):
    """Get all VPS instances for a user."""
    try:
        vps_list = VPS.query.filter_by(user_id=user_id).all()
        return jsonify({
            "message": "VPS obtenidos exitosamente",
            "vps": [v.to_dict() for v in vps_list]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# @vps_bp.route('/sync', methods=['POST'])
@session_or_token_required
def sync_vps():
    """Sync VPS instances from Contabo to local database."""
    try:
        current_user = request.current_user
        
        # Get Contabo config for user
        config = ContaboConfig.query.filter_by(user_id=current_user.id).first()
        if not config:
            return jsonify({"error": "Configuración de Contabo no encontrada"}), 404
        
        # Decrypt credentials
        client_secret = contabo_encrypt_service.decrypt(config.client_secret)
        password = contabo_encrypt_service.decrypt(config.password)
        
        if not client_secret or not password:
            return jsonify({"error": "Error al descifrar credenciales"}), 500
        
        # Create service and sync
        service = ContaboService(
            client_id=config.client_id,
            client_secret=client_secret,
            username=config.username,
            password=password
        )
        
        result = sync_instances_to_db(current_user.id, service)
        
        return jsonify({
            "message": "Sincronización completada",
            "result": result
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error en sincronización: {str(e)}"}), 500


# @vps_bp.route('/<int:vps_id>/restart', methods=['POST'])
@session_or_token_required
def restart_vps(vps_id):
    """Restart a VPS instance."""
    try:
        current_user = request.current_user
        
        # Verify VPS belongs to user
        vps = VPS.query.filter_by(id=vps_id, user_id=current_user.id).first()
        if not vps:
            return jsonify({"error": "VPS no encontrado"}), 404
        
        # Get Contabo config
        config = ContaboConfig.query.filter_by(user_id=current_user.id).first()
        if not config:
            return jsonify({"error": "Configuración de Contabo no encontrada"}), 404
        
        # Decrypt credentials
        client_secret = contabo_encrypt_service.decrypt(config.client_secret)
        password = contabo_encrypt_service.decrypt(config.password)
        
        if not client_secret or not password:
            return jsonify({"error": "Error al descifrar credenciales"}), 500
        
        # Create service and restart
        service = ContaboService(
            client_id=config.client_id,
            client_secret=client_secret,
            username=config.username,
            password=password
        )
        
        result = service.restart_instance(vps.instance_id)
        
        return jsonify({
            "message": "Reinicio solicitado exitosamente",
            "result": result
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al reiniciar: {str(e)}"}), 500
