import os
from flask import Flask
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

    # Usar ADMIN_KEY como clave secreta
    app.config['SECRET_KEY'] = os.getenv('ADMIN_KEY')


    # Determinar si estamos en producción o desarrollo
    is_production = os.getenv('FLASK_ENV') == 'production'

    # Obtener la ruta de la base de datos desde las variables de entorno
    database_path = os.getenv(
        'DATABASE_PATH' if is_production else 'DATABASE_PATH_DEV'
    )

    # Si la ruta no es absoluta, convertirla a absoluta
    if not os.path.isabs(database_path):
        basedir = os.path.abspath(os.path.dirname(__file__))
        database_path = os.path.join(basedir, database_path)

    # Configuración de SQLAlchemy
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{database_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Crear el directorio de la base de datos si no existe
    database_dir = os.path.dirname(database_path)
    try:
        os.makedirs(database_dir, exist_ok=True)
    except OSError as e:
        print(f"Error al crear el directorio de la base de datos: {e}")
        raise e

    # Registrar los blueprints
    app.register_blueprint(auth_bp)

    # Inicializar la base de datos
    init_db(app)

    # Configurar Flask-Migrate
    migrate = Migrate(app, db)

    return app


# Crear la aplicación
app = create_app()
