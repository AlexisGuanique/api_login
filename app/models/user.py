from datetime import datetime
from app.database import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=True)  # Nuevo campo para el nombre
    lastname = db.Column(db.String(100), nullable=True)  # Nuevo campo para el apellido
    access_token = db.Column(db.Text, nullable=True)
    token_expiration = db.Column(db.DateTime, nullable=True)
