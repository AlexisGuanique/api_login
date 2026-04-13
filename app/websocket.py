from datetime import datetime
from flask import request
from flask_socketio import emit, disconnect
from app.database import db
from app.models.bot import Bot
from app.models.user import User
from app.models.bot_browser_presence import BotBrowserPresence
from app.models.bot_domain_global_config import BotDomainGlobalConfig
from app.models.bot_domain_entry import BotDomainEntry
from app.models.bot_random_tld_entry import BotRandomTldEntry
import jwt
from sqlalchemy.dialects.sqlite import insert as sqlite_insert


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
        """Maneja la desconexión de un bot sin escribir en el socket cerrado."""
        try:
            socket_id = request.sid
        except Exception:
            print("⚠️  Desconexión sin socket_id disponible")
            return

        try:
            bot = Bot.query.filter_by(socket_id=socket_id).first()
            if not bot:
                print(f"⚠️  Desconexión de socket desconocido: {socket_id}")
                return

            bot_id = bot.id
            user_id = bot.user_id
            bot_name = bot.name

            bot.status = 'offline'
            bot.socket_id = None
            bot.last_seen = datetime.utcnow()
            db.session.commit()
            print(f"🔌 Bot desconectado: {bot_name} (ID: {bot_id})")

            # Notificar solo a UIs web; errores aquí no deben romper el disconnect.
            try:
                socketio.emit('bot_status_changed', {
                    'bot_id': bot_id,
                    'status': 'offline',
                    'user_id': user_id
                }, room=f'user_{user_id}')
            except Exception as emit_error:
                print(f"⚠️  No se pudo notificar desconexión a UI: {emit_error}")
        except Exception as e:
            print(f"❌ Error en disconnect: {e}")
            import traceback
            traceback.print_exc()
            try:
                db.session.rollback()
            except Exception:
                pass
    
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
    
    @socketio.on('action_completed')
    def handle_action_completed(data):
        """Recibe confirmaciones de acciones completadas por el bot"""
        try:
            bot = Bot.query.filter_by(socket_id=request.sid).first()
            if not bot:
                print(f"⚠️  action_completed recibido de socket desconocido: {request.sid}")
                return
            
            action = data.get('action', 'unknown')
            success = data.get('success', False)
            message = data.get('message', '')
            
            print(f"📨 Acción completada: {bot.name} -> {action} (success: {success})")
            
            # Reenviar la confirmación a la UI del usuario
            socketio.emit('bot_action_completed', {
                'bot_id': bot.id,
                'bot_name': bot.name,
                'action': action,
                'success': success,
                'message': message,
                'user_id': bot.user_id
            }, room=f'user_{bot.user_id}')
            
        except Exception as e:
            print(f"❌ Error en action_completed: {e}")
            import traceback
            traceback.print_exc()

    @socketio.on('sync_available_browsers')
    def handle_sync_available_browsers(data):
        """Recibe y guarda navegadores disponibles reportados por el bot."""
        try:
            bot = Bot.query.filter_by(socket_id=request.sid).first()
            if not bot:
                print(f"⚠️  sync_available_browsers recibido de socket desconocido: {request.sid}")
                return

            raw_browsers = data.get('browsers', []) if isinstance(data, dict) else []
            if not isinstance(raw_browsers, list):
                print("⚠️  Formato inválido en sync_available_browsers: 'browsers' debe ser lista")
                return

            normalized = []
            seen = set()
            for name in raw_browsers:
                if not isinstance(name, str):
                    continue
                clean = name.strip()
                if not clean:
                    continue
                key = clean.lower()
                if key in seen:
                    continue
                seen.add(key)
                normalized.append(clean)

            if not normalized:
                return

            now = datetime.utcnow()
            incoming_names = set(normalized)

            # UPSERT por navegador (evita duplicados incluso con concurrencia).
            for browser_name in incoming_names:
                stmt = sqlite_insert(BotBrowserPresence).values(
                    user_id=bot.user_id,
                    bot_id=bot.id,
                    browser_name=browser_name,
                    last_seen=now,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=['bot_id', 'browser_name'],
                    set_={'last_seen': now, 'user_id': bot.user_id}
                )
                db.session.execute(stmt)

            # Eliminar navegadores que este bot ya no reporta.
            base_query = BotBrowserPresence.query.filter_by(bot_id=bot.id)
            if incoming_names:
                base_query = base_query.filter(~BotBrowserPresence.browser_name.in_(incoming_names))
            base_query.delete(synchronize_session=False)

            db.session.commit()
            print(
                f"✅ Catálogo de navegadores sincronizado para user_id={bot.user_id}, "
                f"bot_id={bot.id}: {len(incoming_names)} activos"
            )
        except Exception as e:
            print(f"❌ Error en sync_available_browsers: {e}")
            try:
                db.session.rollback()
            except:
                pass

    @socketio.on('sync_domain_config')
    def handle_sync_domain_config(data):
        """Sincroniza catálogo de dominios y configuración global reportada por el bot."""
        try:
            bot = Bot.query.filter_by(socket_id=request.sid).first()
            if not bot:
                print(f"⚠️  sync_domain_config recibido de socket desconocido: {request.sid}")
                return

            if not isinstance(data, dict):
                print("⚠️  Formato inválido en sync_domain_config")
                return

            payload_global = data.get('global_config') or {}
            payload_domains = data.get('domains') or []
            payload_tlds = data.get('random_tlds') or []

            global_cfg = BotDomainGlobalConfig.query.filter_by(user_id=bot.user_id).first()
            if not global_cfg:
                global_cfg = BotDomainGlobalConfig(
                    user_id=bot.user_id,
                    is33mail=bool(payload_global.get('is33mail', True)),
                    random_domains=bool(payload_global.get('random_domains', False)),
                    fill_domain=bool(payload_global.get('fill_domain', False)),
                    domain=(payload_global.get('domain') or None),
                )
                db.session.add(global_cfg)

            # Solo sembrar dominios desde el bot si el usuario aún no tiene filas en el panel.
            # Si ya hay dominios en servidor (editados/guardados en la web), no pisar:
            # si no, el bot volvería a insertar p. ej. @gmail.com y anularía Rellenar/Activo u otros dominios.
            existing_domain_count = BotDomainEntry.query.filter_by(user_id=bot.user_id).count()
            if existing_domain_count == 0:
                normalized_domains = []
                seen_domains = set()
                for row in payload_domains:
                    if not isinstance(row, dict):
                        continue
                    domain_name = str(row.get('domain') or '').strip()
                    if not domain_name:
                        continue
                    if not domain_name.startswith('@'):
                        domain_name = f"@{domain_name}"
                    key = domain_name.lower()
                    if key in seen_domains:
                        continue
                    seen_domains.add(key)
                    normalized_domains.append({
                        'domain': domain_name,
                        'fill_domain': bool(row.get('fill_domain', False)),
                        'is_active': bool(row.get('is_active', True)),
                    })

                for row in normalized_domains:
                    stmt = sqlite_insert(BotDomainEntry).values(
                        user_id=bot.user_id,
                        domain=row['domain'],
                        fill_domain=row['fill_domain'],
                        is_active=row['is_active'],
                    )
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['user_id', 'domain'],
                        set_={
                            'fill_domain': row['fill_domain'],
                            'is_active': row['is_active'],
                        }
                    )
                    db.session.execute(stmt)

            existing_tld_count = BotRandomTldEntry.query.filter_by(user_id=bot.user_id).count()
            if existing_tld_count == 0:
                normalized_tlds = []
                seen_tlds = set()
                for index, row in enumerate(payload_tlds):
                    value = row.get('tld') if isinstance(row, dict) else row
                    tld = str(value or '').strip().lstrip('.').lower()
                    if not tld:
                        continue
                    if tld in seen_tlds:
                        continue
                    seen_tlds.add(tld)
                    normalized_tlds.append({'tld': tld, 'sort_order': index})

                for row in normalized_tlds:
                    stmt = sqlite_insert(BotRandomTldEntry).values(
                        user_id=bot.user_id,
                        tld=row['tld'],
                        sort_order=row['sort_order'],
                    )
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['user_id', 'tld'],
                        set_={'sort_order': row['sort_order']}
                    )
                    db.session.execute(stmt)

            db.session.commit()
            print(
                f"✅ Config de dominios sincronizada user_id={bot.user_id}: "
                f"dominios_bot={'omitidos (ya hay tabla en servidor)' if existing_domain_count else 'aplicados'}, "
                f"tlds_bot={'omitidos (ya hay TLDs en servidor)' if existing_tld_count else 'aplicados'}"
            )
        except Exception as e:
            print(f"❌ Error en sync_domain_config: {e}")
            try:
                db.session.rollback()
            except:
                pass

