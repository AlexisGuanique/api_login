from datetime import datetime
from app.database import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    access_token = db.Column(db.Text, nullable=True)
    token_expiration = db.Column(db.DateTime, nullable=True)
