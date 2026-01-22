import os
from flask import Blueprint, request, jsonify, current_app
from app.database import db
from app.models.bot import Bot
from app.models.user import User
from app.utils.auth import token_required, session_or_token_required
from datetime import datetime

bots_bp = Blueprint('bots', __name__, url_prefix='/api/bots')


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
        
        # Enviar comando vía WebSocket
        socketio = current_app.socketio
        socketio.emit('command', {
            'command': command,
            'bot_id': bot_id
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

