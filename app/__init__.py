import os
from flask import Flask, jsonify
from flask_migrate import Migrate
from app.controllers.users import auth_bp
from app.database import init_db
from app.database import db
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()


def create_app():
    app = Flask(__name__)
    CORS(app)

    app.config['SECRET_KEY'] = os.getenv('ADMIN_KEY')


    is_production = os.getenv('FLASK_ENV') == 'production'

    database_path = os.getenv(
        'DATABASE_PATH' if is_production else 'DATABASE_PATH_DEV'
    )

    if not os.path.isabs(database_path):
        basedir = os.path.abspath(os.path.dirname(__file__))
        database_path = os.path.join(basedir, database_path)

    # Configuración de SQLAlchemy
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{database_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    database_dir = os.path.dirname(database_path)
    try:
        os.makedirs(database_dir, exist_ok=True)
    except OSError as e:
        print(f"Error al crear el directorio de la base de datos: {e}")
        raise e

    app.register_blueprint(auth_bp)

    init_db(app)

    migrate = Migrate(app, db)

    @app.route('/')
    def home():
        return jsonify(message="Hola Trueno. Api Login")

    

    return app


# Crear la aplicación
app = create_app()
