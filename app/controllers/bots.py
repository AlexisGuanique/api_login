import json
import os

from flask import Blueprint, request, jsonify, current_app
from app.database import db
from app.models.bot import Bot
from app.models.bot_global_config import BotGlobalConfig
from app.models.bot_domain_global_config import BotDomainGlobalConfig
from app.models.bot_domain_entry import BotDomainEntry
from app.models.bot_random_tld_entry import BotRandomTldEntry
from app.utils.auth import token_required, session_or_token_required
from app.utils.bot_preferences import get_preferred_browsers_list

bots_bp = Blueprint('bots', __name__, url_prefix='/api/bots')


def _build_remote_creator_time_config(user_id: int) -> dict:
    """
    Valores que el bot aplica en SQLite (global_time_config) al recibir execute_creator.
    Si no hay fila o campos nulos, por defecto: ciclo continuo (0 min), 1 cuenta/ciclo.
    """
    g = BotGlobalConfig.query.filter_by(user_id=user_id).first()
    default_type = "cycle"
    default_cycle = 0
    default_apc = 1
    if not g:
        return {
            "scheduled_time": None,
            "timezone": None,
            "cycle_time_minutes": default_cycle,
            "time_config_type": default_type,
            "accounts_per_cycle": default_apc,
        }
    raw_type = (g.creator_time_config_type or default_type).strip().lower()
    if raw_type not in ("manual", "scheduled", "cycle", "both"):
        raw_type = default_type
    cm = g.creator_cycle_time_minutes
    if cm is None:
        cm = default_cycle
    apc = g.creator_accounts_per_cycle
    if apc is None:
        apc = default_apc
    return {
        "scheduled_time": g.creator_scheduled_time,
        "timezone": g.creator_timezone,
        "cycle_time_minutes": int(cm),
        "time_config_type": raw_type,
        "accounts_per_cycle": int(apc),
    }


def _build_remote_creator_user_agents_by_browser(user_id: int) -> dict[str, str]:
    g = BotGlobalConfig.query.filter_by(user_id=user_id).first()
    if not g or not g.creator_user_agents_by_browser_json:
        return {}
    try:
        data = json.loads(g.creator_user_agents_by_browser_json)
    except (TypeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, str):
            kk = k.strip()
            vv = v.strip()
            if kk and vv:
                out[kk] = vv
    return out


def _build_remote_creator_user_agents_legacy_list(user_id: int) -> list[str]:
    """Lista legacy (columna creator_user_agents_json); respaldo si no hay mapa por navegador."""
    g = BotGlobalConfig.query.filter_by(user_id=user_id).first()
    if not g or not g.creator_user_agents_json:
        return []
    try:
        data = json.loads(g.creator_user_agents_json)
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    result: list[str] = []
    for item in data:
        if isinstance(item, str):
            ua = item.strip()
            if ua:
                result.append(ua)
    return result


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
        preferred_browsers = get_preferred_browsers_list(global_config)
        preferred_browser = preferred_browsers[0] if preferred_browsers else None

        by_browser = _build_remote_creator_user_agents_by_browser(request.current_user.id)
        legacy_list = _build_remote_creator_user_agents_legacy_list(request.current_user.id)
        ua_for_preferred = None
        if preferred_browser and by_browser:
            ua_for_preferred = by_browser.get(preferred_browser)
        if not ua_for_preferred and legacy_list:
            ua_for_preferred = legacy_list[0]

        # Enviar comando vía WebSocket
        socketio = current_app.socketio
        payload = {
            'command': command,
            'bot_id': bot_id,
            'preferred_browser': preferred_browser,
            'preferred_browsers': preferred_browsers,
            'remote_domain_config': _build_remote_domain_config(request.current_user.id),
        }
        if command == 'execute_creator':
            payload['remote_creator_time_config'] = _build_remote_creator_time_config(
                request.current_user.id
            )
            payload['remote_creator_user_agents_by_browser'] = by_browser
            payload['remote_creator_user_agent'] = ua_for_preferred
            payload['remote_creator_user_agents'] = (
                list(by_browser.values()) if by_browser else legacy_list
            )
            # Debug temporal: habilitar con BOT_CREATOR_UA_DEBUG=true
            if os.getenv("BOT_CREATOR_UA_DEBUG", "false").lower() == "true":
                ua_dbg = (
                    (ua_for_preferred[:120] + "…")
                    if ua_for_preferred
                    else None
                )
                print(
                    f"🐞 DEBUG creator UA -> user_id={request.current_user.id}, "
                    f"bot_id={bot_id}, preferred_browser={preferred_browser!r}, "
                    f"ua_for_preferred={ua_dbg!r}, "
                    f"by_browser_keys={list(by_browser.keys())[:8]}"
                )
        socketio.emit('command', payload, room=bot.socket_id)
        
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

