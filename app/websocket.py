from datetime import datetime
from flask import request
from flask_socketio import emit, disconnect
from app.database import db
from app.models.bot import Bot
from app.models.user import User
import jwt


def register_socketio_handlers(socketio):
    """Registra todos los handlers de WebSocket"""
    
    @socketio.on('connect')
    def handle_connect(auth=None):
        """Maneja la conexión de un bot"""
        try:
            # Flask-SocketIO puede pasar auth como parámetro o en request.event
            if auth is None:
                # Intentar obtener desde request.event si está disponible
                try:
                    if hasattr(request, 'event') and request.event and 'auth' in request.event:
                        auth = request.event['auth']
                except:
                    pass
            
            # El bot debe enviar access_token en auth
            if not auth or 'access_token' not in auth:
                print(f"❌ Conexión rechazada: auth no válido. auth recibido: {auth}")
                try:
                    disconnect()
                except:
                    pass  # Si ya está desconectado, ignorar
                return False
            
            token = auth['access_token']
            bot_name = auth.get('bot_name', '').strip()
            bot_type = auth.get('bot_type', 'logueador').strip().lower()  # 'creador' o 'logueador'
            
            # Validar nombre del bot
            if not bot_name:
                print("❌ Conexión rechazada: bot_name vacío o no proporcionado")
                try:
                    disconnect()
                except:
                    pass
                return False
            
            # Validar tipo de bot
            if bot_type not in ['creador', 'logueador']:
                print(f"❌ Conexión rechazada: bot_type inválido: {bot_type}. Debe ser 'creador' o 'logueador'")
                try:
                    disconnect()
                except:
                    pass
                return False
            
            print(f"🔌 Intento de conexión: bot_name={bot_name}, bot_type={bot_type}")
            
            # Validar token
            from flask import current_app
            try:
                payload = jwt.decode(
                    token,
                    current_app.config['SECRET_KEY'],
                    algorithms=['HS256'],
                    options={'verify_exp': False}
                )
                username = payload.get('username')
                if not username:
                    try:
                        disconnect()
                    except:
                        pass
                    return False
                
                # Buscar usuario
                user = User.query.filter_by(username=username).first()
                if not user or user.access_token != token:
                    try:
                        disconnect()
                    except:
                        pass
                    return False
                
                # Buscar bot existente con el mismo nombre y tipo para este usuario
                bot = Bot.query.filter_by(
                    user_id=user.id,
                    name=bot_name,
                    bot_type=bot_type
                ).first()
                
                # Si hay otro bot con el mismo nombre pero diferente socket_id, desconectarlo primero
                if bot and bot.socket_id and bot.socket_id != request.sid:
                    print(f"⚠️  Bot '{bot_name}' ya tiene una conexión activa (socket_id: {bot.socket_id}). Actualizando...")
                    # Notificar al cliente web que el bot anterior se desconectó
                    try:
                        socketio.emit('bot_status_changed', {
                            'bot_id': bot.id,
                            'status': 'offline',
                            'user_id': user.id
                        }, room=f'user_{user.id}')
                    except:
                        pass
                    # Limpiar socket_id del bot anterior
                    bot.socket_id = None
                    bot.status = 'offline'
                    bot.last_seen = datetime.utcnow()
                
                # Si no existe el bot con ese nombre, buscar un bot offline del mismo usuario y tipo
                # para reutilizar su ID (solo actualizar el nombre)
                if not bot:
                    # Buscar un bot offline del mismo usuario y tipo
                    offline_bot = Bot.query.filter_by(
                        user_id=user.id,
                        bot_type=bot_type,
                        status='offline'
                    ).filter(
                        (Bot.socket_id.is_(None)) | (Bot.socket_id == '')
                    ).first()
                    
                    if offline_bot:
                        # Reutilizar el bot existente, actualizando solo el nombre
                        # La ID se mantiene constante
                        old_name = offline_bot.name
                        offline_bot.name = bot_name
                        bot = offline_bot
                        print(f"✅ Bot existente reutilizado (ID: {bot.id}): nombre actualizado de '{old_name}' a '{bot_name}' ({bot_type}) para usuario {user.username}")
                    else:
                        # No hay ningún bot offline, crear uno nuevo
                        bot = Bot(
                            user_id=user.id,
                            name=bot_name,
                            bot_type=bot_type,
                            status='online'
                        )
                        db.session.add(bot)
                        print(f"✅ Nuevo bot creado: {bot_name} ({bot_type}) para usuario {user.username}")
                else:
                    print(f"✅ Bot existente actualizado: {bot_name} ({bot_type}) para usuario {user.username}")
                
                # Actualizar bot con conexión actual
                bot.socket_id = request.sid
                bot.status = 'online'
                bot.last_seen = datetime.utcnow()
                db.session.commit()
                
                # Verificar que el commit fue exitoso
                if not bot.id:
                    print("❌ Error: No se pudo obtener el ID del bot después del commit")
                    try:
                        disconnect()
                    except:
                        pass
                    return False
                
                # Confirmar conexión
                print(f"✅ Bot conectado exitosamente: {bot_name} (ID: {bot.id})")
                emit('connected', {
                    'bot_id': bot.id,
                    'status': 'online',
                    'message': 'Conexión establecida'
                })
                
                # Notificar a otros clientes web del usuario
                socketio.emit('bot_status_changed', {
                    'bot_id': bot.id,
                    'status': 'online',
                    'user_id': user.id
                }, room=f'user_{user.id}')
                
                return True
                
            except jwt.InvalidTokenError as e:
                print(f"❌ Token inválido: {e}")
                try:
                    disconnect()
                except:
                    pass
                return False
            except Exception as e:
                print(f"❌ Error al validar token: {e}")
                try:
                    disconnect()
                except:
                    pass
                return False
                
        except Exception as e:
            print(f"❌ Error en connect: {e}")
            import traceback
            traceback.print_exc()
            try:
                disconnect()
            except:
                pass
            return False
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Maneja la desconexión de un bot"""
        import threading
        import time
        from flask import current_app
        
        # Capturar socket_id ANTES de iniciar el thread (request.sid solo está disponible en el contexto actual)
        socket_id = None
        try:
            socket_id = request.sid
        except:
            print("⚠️  Desconexión sin socket_id disponible")
            return
        
        # Obtener información del bot ANTES de iniciar el thread
        bot = None
        bot_id = None
        user_id = None
        bot_name = None
        app_instance = None
        try:
            bot = Bot.query.filter_by(socket_id=socket_id).first()
            if bot:
                bot_name = bot.name
                bot_id = bot.id
                user_id = bot.user_id
            # Capturar la instancia de la aplicación para usar en el thread
            app_instance = current_app._get_current_object()
        except Exception as e:
            print(f"⚠️  Error al obtener bot: {e}")
            return
        
        if not bot:
            print(f"⚠️  Desconexión de socket desconocido: {socket_id}")
            return
        
        def process_disconnect(app, sid, bid, uid, name):
            """Procesa la desconexión en un thread separado para evitar errores de escritura"""
            # Usar application context para poder acceder a la base de datos
            with app.app_context():
                try:
                    # Pequeño delay para asegurar que la desconexión se complete
                    time.sleep(0.2)
                    
                    print(f"🔌 Bot desconectado: {name} (ID: {bid})")
                    
                    # Actualizar estado del bot en la base de datos
                    try:
                        # Re-obtener el bot para asegurar que tenemos la versión más reciente
                        current_bot = Bot.query.filter_by(id=bid).first()
                        if current_bot:
                            current_bot.status = 'offline'
                            current_bot.socket_id = None
                            current_bot.last_seen = datetime.utcnow()
                            db.session.commit()
                    except Exception as db_error:
                        print(f"⚠️  Error al actualizar bot en BD: {db_error}")
                        db.session.rollback()
                    
                    # Notificar a clientes web usando emit con skip_sid para evitar errores
                    try:
                        socketio.emit('bot_status_changed', {
                            'bot_id': bid,
                            'status': 'offline',
                            'user_id': uid
                        }, room=f'user_{uid}', skip_sid=sid)
                    except Exception as emit_error:
                        # Si falla el emit, no es crítico - la conexión ya se cerró
                        print(f"⚠️  No se pudo notificar desconexión (conexión ya cerrada): {emit_error}")
                except Exception as e:
                    print(f"❌ Error en disconnect: {e}")
                    import traceback
                    traceback.print_exc()
                    # Asegurar rollback en caso de error
                    try:
                        db.session.rollback()
                    except:
                        pass
        
        # Procesar la desconexión en un thread separado con un pequeño delay
        # para evitar errores de "write() before start_response"
        try:
            threading.Thread(target=process_disconnect, args=(app_instance, socket_id, bot_id, user_id, bot_name), daemon=True).start()
        except Exception as e:
            print(f"⚠️  Error al iniciar thread de desconexión: {e}")
            # Si falla el thread, simplemente registrar la desconexión sin procesar
            print(f"🔌 Bot desconectado: {bot_name} (ID: {bot_id})")
    
    @socketio.on('status_update')
    def handle_status_update(data):
        """Recibe actualizaciones de estado del bot"""
        try:
            bot = Bot.query.filter_by(socket_id=request.sid).first()
            if not bot:
                print(f"⚠️  status_update recibido de socket desconocido: {request.sid}")
                return
            
            new_status = data.get('status', bot.status)
            if new_status not in ['online', 'offline', 'running', 'stopped']:
                print(f"⚠️  Estado inválido recibido: {new_status}")
                return
            
            # Debug: mostrar datos recibidos
            if 'next_cycle_at' in data:
                print(f"📨 status_update recibido de {bot.name}: status={new_status}, next_cycle_at={data.get('next_cycle_at')}")
            
            # Actualizar estado del bot
            bot.status = new_status
            bot.last_seen = datetime.utcnow()
            
            # Actualizar next_cycle_at si se proporciona (solo para logueadores)
            if bot.bot_type == 'logueador':
                if 'next_cycle_at' in data:
                    next_cycle_str = data.get('next_cycle_at')
                    if next_cycle_str:
                        try:
                            # Parsear la fecha ISO string a datetime UTC
                            if next_cycle_str.endswith('Z'):
                                next_cycle_str = next_cycle_str[:-1] + '+00:00'
                            elif '+' not in next_cycle_str and '-' not in next_cycle_str[-6:]:
                                next_cycle_str = next_cycle_str + '+00:00'
                            from dateutil import parser
                            bot.next_cycle_at = parser.isoparse(next_cycle_str)
                            print(f"📅 Próximo ciclo actualizado: {bot.name} -> {bot.next_cycle_at}")
                        except Exception as e:
                            print(f"⚠️  Error al parsear next_cycle_at: {e}")
                    else:
                        # Si se envía None o vacío, limpiar el campo
                        bot.next_cycle_at = None
                elif new_status in ['stopped', 'offline']:
                    # Limpiar next_cycle_at cuando el bot se detiene o desconecta
                    bot.next_cycle_at = None
            
            db.session.commit()
            
            # Notificar a clientes web
            socketio.emit('bot_status_changed', {
                'bot_id': bot.id,
                'status': new_status,
                'next_cycle_at': bot.next_cycle_at.isoformat() + 'Z' if bot.next_cycle_at else None,
                'user_id': bot.user_id
            }, room=f'user_{bot.user_id}')
            
            print(f"✅ Estado actualizado: {bot.name} -> {new_status}")
            if bot.next_cycle_at:
                print(f"   📅 next_cycle_at guardado: {bot.next_cycle_at}")
            
        except Exception as e:
            print(f"❌ Error en status_update: {e}")
            import traceback
            traceback.print_exc()
            try:
                db.session.rollback()
            except:
                pass
    
    @socketio.on('join_user_room')
    def handle_join_user_room(data):
        """Permite a clientes web unirse a la sala del usuario"""
        try:
            user_id = data.get('user_id')
            if user_id:
                from flask import session
                # Verificar que el user_id de la sesión coincida
                if session.get('user_id') == user_id:
                    socketio.server.enter_room(request.sid, f'user_{user_id}')
                    emit('joined_room', {'room': f'user_{user_id}'})
        except Exception as e:
            print(f"❌ Error en join_user_room: {e}")
            import traceback
            traceback.print_exc()

