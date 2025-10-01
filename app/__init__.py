import os
from flask import Flask, jsonify
from flask_migrate import Migrate
from app.controllers.users import auth_bp
from app.controllers.emails import emails_bp
from app.database import init_db
from app.database import db
from flask_cors import CORS
from dotenv import load_dotenv

# Importar modelos para que las migraciones los detecten
from app.models.user import User
from app.models.email import Email

load_dotenv()


def create_app():
    app = Flask(__name__)
    CORS(app)

    app.config['SECRET_KEY'] = os.getenv('ADMIN_KEY', 'my_very_secret_key')

    # Configuración de SQLAlchemy
    database_path = os.getenv('DATABASE_PATH', '/api_login/app/database')
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

    init_db(app)

    migrate = Migrate(app, db)

    @app.route('/')
    def home():
        return jsonify(message="Hola Trueno. Api Login")

    

    return app


# Crear la aplicación
app = create_app()
