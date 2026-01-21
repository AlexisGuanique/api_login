import os
from flask import Flask, jsonify, redirect, url_for
from flask_migrate import Migrate
from app.controllers.users import auth_bp
from app.controllers.emails import emails_bp
from app.controllers.accounts import accounts_bp
from app.web import web_bp
from app.database import init_db
from app.database import db
from flask_cors import CORS
from dotenv import load_dotenv

# Importar modelos para que las migraciones los detecten
from app.models.user import User
from app.models.email import Email
from app.models.account import Account

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
    app.register_blueprint(web_bp, url_prefix="/web")

    init_db(app)

    migrate = Migrate(app, db)

    @app.route('/')
    def home():
        return redirect(url_for('web.login'))

    

    return app


# Crear la aplicación
app = create_app()
