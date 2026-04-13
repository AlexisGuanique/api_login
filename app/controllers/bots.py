from flask import Blueprint, request, jsonify, current_app
from app.database import db
from app.models.bot import Bot
from app.models.bot_global_config import BotGlobalConfig
from app.models.bot_browser_user_agent import BotBrowserUserAgent
from app.models.bot_domain_global_config import BotDomainGlobalConfig
from app.models.bot_domain_entry import BotDomainEntry
from app.models.bot_random_tld_entry import BotRandomTldEntry
from app.utils.auth import token_required, session_or_token_required

bots_bp = Blueprint('bots', __name__, url_prefix='/api/bots')


def _build_remote_domain_config(user_id: int) -> dict:
    global_cfg = BotDomainGlobalConfig.query.filter_by(user_id=user_id).first()
    domain_rows = (
        BotDomainEntry.query
        .filter_by(user_id=user_id)
        .order_by(BotDomainEntry.id.asc())
        .all()
    )
    tld_rows = (
        BotRandomTldEntry.query
        .filter_by(user_id=user_id)
        .order_by(BotRandomTldEntry.sort_order.asc(), BotRandomTldEntry.id.asc())
        .all()
    )
    return {
        "global_config": {
            "is33mail": bool(global_cfg.is33mail) if global_cfg else True,
            "random_domains": bool(global_cfg.random_domains) if global_cfg else False,
            "fill_domain": bool(global_cfg.fill_domain) if global_cfg else False,
            "domain": global_cfg.domain if global_cfg else None,
        },
        "domains": [
            {
                "domain": row.domain,
                "fill_domain": bool(row.fill_domain),
                "is_active": bool(row.is_active),
            }
            for row in domain_rows
        ],
        "random_tlds": [
            {"tld": row.tld, "sort_order": int(row.sort_order or 0)}
            for row in tld_rows
        ],
    }


#! ENDPOINT PARA OBTENER TODOS LOS BOTS DE UN USUARIO
@bots_bp.route('/user/<int:user_id>', methods=['POST'])
@token_required
def get_user_bots(user_id):
    """Obtiene todos los bots de un usuario"""
    try:
        bots = Bot.query.filter_by(user_id=user_id).order_by(Bot.last_seen.desc()).all()
        
        bots_list = [bot.to_dict() for bot in bots]
        
        return jsonify({
            "message": "Bots obtenidos exitosamente",
            "user_id": user_id,
            "bots": bots_list,
            "count": len(bots_list)
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al obtener los bots: {str(e)}"}), 500


#! ENDPOINT PARA OBTENER TODOS LOS BOTS DEL USUARIO ACTUAL (vía sesión)
@bots_bp.route('/status', methods=['GET'])
@session_or_token_required
def get_bots_status():
    """Obtiene el estado actual de todos los bots del usuario autenticado"""
    try:
        user_id = request.current_user.id
        bots = Bot.query.filter_by(user_id=user_id).order_by(Bot.last_seen.desc()).all()
        
        bots_list = [bot.to_dict() for bot in bots]
        
        return jsonify({
            "message": "Estado de bots obtenido exitosamente",
            "user_id": user_id,
            "bots": bots_list,
            "count": len(bots_list)
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al obtener el estado de los bots: {str(e)}"}), 500


#! ENDPOINT PARA ENVIAR COMANDO A UN BOT
@bots_bp.route('/command/<int:bot_id>', methods=['POST'])
@session_or_token_required
def send_command(bot_id):
    """Envía un comando a un bot específico (start, stop, etc.)"""
    try:
        data = request.json
        command = data.get('command')
        
        if not command:
            return jsonify({"error": "Comando requerido"}), 400
        
        bot = Bot.query.filter_by(id=bot_id).first()
        if not bot:
            return jsonify({"error": "Bot no encontrado"}), 404
        
        # Verificar que el bot pertenece al usuario autenticado
        if bot.user_id != request.current_user.id:
            return jsonify({"error": "No autorizado"}), 403
        
        # Verificar que el bot está conectado
        if not bot.socket_id or bot.status == 'offline':
            return jsonify({"error": "Bot no está conectado"}), 400
        
        # Verificar el estado actual del bot antes de enviar el comando
        # Si el bot ya está en el estado deseado, devolver el estado real sin enviar comando
        if command == 'start' or command == 'execute_creator':
            if bot.status == 'running':
                return jsonify({
                    "message": f"El bot ya se está ejecutando. No se puede iniciar otro.",
                    "bot_id": bot_id,
                    "command": command,
                    "current_status": bot.status,
                    "status_synced": True
                }), 200
        elif command == 'stop':
            if bot.status == 'stopped':
                return jsonify({
                    "message": f"El bot ya está detenido.",
                    "bot_id": bot_id,
                    "command": command,
                    "current_status": bot.status,
                    "status_synced": True
                }), 200
        
        global_config = BotGlobalConfig.query.filter_by(user_id=request.current_user.id).first()
        preferred_browser = global_config.preferred_browser if global_config else None
        user_agent = None
        if preferred_browser:
            ua_cfg = BotBrowserUserAgent.query.filter_by(
                user_id=request.current_user.id,
                browser_name=preferred_browser
            ).first()
            user_agent = ua_cfg.user_agent if ua_cfg else None

        # Enviar comando vía WebSocket
        socketio = current_app.socketio
        socketio.emit('command', {
            'command': command,
            'bot_id': bot_id,
            'preferred_browser': preferred_browser,
            'remote_user_agent': user_agent,
            'remote_domain_config': _build_remote_domain_config(request.current_user.id),
        }, room=bot.socket_id)
        
        # Devolver el estado actual del bot para sincronizar la UI
        return jsonify({
            "message": f"Comando '{command}' enviado al bot",
            "bot_id": bot_id,
            "command": command,
            "current_status": bot.status
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al enviar comando: {str(e)}"}), 500


#! ENDPOINT PARA ELIMINAR UN BOT
@bots_bp.route('/<int:bot_id>', methods=['DELETE'])
@session_or_token_required
def delete_bot(bot_id):
    """Elimina un bot"""
    try:
        bot = Bot.query.filter_by(id=bot_id).first()
        if not bot:
            return jsonify({"error": "Bot no encontrado"}), 404
        
        # Verificar que el bot pertenece al usuario autenticado
        if bot.user_id != request.current_user.id:
            return jsonify({"error": "No autorizado"}), 403
        
        db.session.delete(bot)
        db.session.commit()
        
        return jsonify({
            "message": "Bot eliminado exitosamente",
            "bot_id": bot_id
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al eliminar el bot: {str(e)}"}), 500

