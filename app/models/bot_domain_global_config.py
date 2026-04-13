from datetime import datetime
from app.database import db


class BotDomainGlobalConfig(db.Model):
    """Configuración global de dominios por usuario."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    is33mail = db.Column(db.Boolean, nullable=False, default=True)
    random_domains = db.Column(db.Boolean, nullable=False, default=False)
    fill_domain = db.Column(db.Boolean, nullable=False, default=False)
    domain = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
