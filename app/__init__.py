import os
from flask import Flask, jsonify, redirect, url_for
from flask_migrate import Migrate
from flask_socketio import SocketIO
from app.controllers.users import auth_bp
from app.controllers.emails import emails_bp
from app.controllers.accounts import accounts_bp
from app.controllers.bots import bots_bp
from app.controllers.proxies import proxies_bp
from app.controllers.vps import vps_bp
from app.controllers.contabo_config import contabo_config_bp
from app.web import web_bp
from app.database import init_db
from app.database import db
from flask_cors import CORS
from dotenv import load_dotenv

# Importar modelos para que las migraciones los detecten
from app.models.user import User
from app.models.email import Email
from app.models.account import Account
from app.models.bot import Bot
from app.models.proxy import Proxy
from app.models.vps import VPS
from app.models.contabo_config import ContaboConfig
from app.models.bot_global_config import BotGlobalConfig
from app.models.bot_browser_catalog import BotBrowserCatalog
from app.models.bot_browser_presence import BotBrowserPresence
from app.models.bot_domain_global_config import BotDomainGlobalConfig
from app.models.bot_domain_entry import BotDomainEntry
from app.models.bot_random_tld_entry import BotRandomTldEntry

load_dotenv()


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    CORS(app)

    # SECRET_KEY para firmar cookies de sesión (debe ser diferente de ADMIN_KEY)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.getenv('ADMIN_KEY', 'my_very_secret_key'))
    
    # Configuración de sesiones para múltiples usuarios/workers
    app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() == 'true'  # True en producción con HTTPS
    app.config['SESSION_COOKIE_HTTPONLY'] = True  # Previene acceso JS a cookies
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Protección CSRF
    app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 30  # 30 días

    # Configuración de SQLAlchemy
    database_path = os.getenv('DATABASE_PATH', 'app/database')
    # En Git Bash sobre Windows, una ruta estilo '/api_login/...' puede resolver
    # hacia 'C:/Program Files/Git/...'. Forzamos una ruta local válida del proyecto.
    if os.name == 'nt' and database_path.startswith('/'):
        print(f"⚠️ DATABASE_PATH inválido para Windows: {database_path}. Usando 'app/database'.")
        database_path = 'app/database'
    # Asegurar que la ruta sea absoluta
    if not os.path.isabs(database_path):
        database_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), database_path)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{database_path}/users.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    database_dir = os.path.dirname(database_path)
    try:
        os.makedirs(database_dir, exist_ok=True)
    except OSError as e:
        print(f"Error al crear el directorio de la base de datos: {e}")
        raise e

    app.register_blueprint(auth_bp)
    app.register_blueprint(emails_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(bots_bp)
    app.register_blueprint(proxies_bp)
    app.register_blueprint(vps_bp)
    app.register_blueprint(contabo_config_bp)
    app.register_blueprint(web_bp, url_prefix="/web")

    init_db(app)

    migrate = Migrate(app, db)
    
    # Inicializar SocketIO para WebSockets
    # Usar 'threading' para desarrollo (compatible con Python 3.13)
    # En producción (Docker) usar 'eventlet' vía variable de entorno
    async_mode = os.getenv('SOCKETIO_ASYNC_MODE', 'threading')
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode=async_mode)
    # Guardar socketio en app para acceso desde otros módulos
    app.socketio = socketio

    @app.route('/')
    def home():
        return redirect(url_for('web.login'))

    

    return app, socketio


# Crear la aplicación y SocketIO
app, socketio = create_app()

# Importar handlers de WebSocket después de crear socketio
from app.websocket import register_socketio_handlers
register_socketio_handlers(socketio)


# Configurar Flask CLI para usar SocketIO cuando se ejecute con 'flask run'
# Esto intercepta el comando run y usa SocketIO en su lugar
import click
from flask.cli import with_appcontext

# Obtener el comando run original de Flask
try:
    from flask.cli import run_command as flask_run_command
except ImportError:
    flask_run_command = None

@click.command('run')
@click.option('--host', '-h', default='127.0.0.1', help='El hostname para bind.')
@click.option('--port', '-p', default=5000, type=int, help='El puerto del servidor.')
@click.option('--debug', is_flag=True, help='Activar modo debug.')
@click.option('--reload', is_flag=True, help='Activar auto-reload.')
@with_appcontext
def socketio_run_command(host, port, debug, reload):
    """Ejecuta el servidor Flask con soporte WebSocket usando SocketIO."""
    print("🚀 Iniciando servidor Flask con WebSockets...")
    print(f"📡 WebSocket habilitado en http://{host}:{port}")
    if debug:
        print("🐛 Modo debug activado")
    socketio.run(
        app,
        host=host,
        port=port,
        debug=debug,
        use_reloader=reload or debug,
        allow_unsafe_werkzeug=True  # Necesario para desarrollo con threading
    )

# Reemplazar el comando run de Flask CLI
try:
    # Intentar reemplazar el comando run
    if hasattr(app, 'cli'):
        # Eliminar el comando run existente si existe
        if 'run' in app.cli.commands:
            del app.cli.commands['run']
        app.cli.add_command(socketio_run_command)
except Exception as e:
    # Si falla, al menos intentar sobrescribir app.run
    print(f"⚠️  No se pudo registrar el comando CLI personalizado: {e}")
    print("   Usa 'python app.py' o 'python -m app' para ejecutar con WebSockets")
    pass