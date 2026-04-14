from datetime import datetime
from app.database import db


class BotGlobalConfig(db.Model):
    """Configuración global de bots por usuario."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    preferred_browser = db.Column(db.String(100), nullable=True)
    # JSON array de nombres, ej. ["Chrome","Firefox"]. Si existe, tiene prioridad sobre preferred_browser.
    preferred_browsers_json = db.Column(db.Text, nullable=True)
    # Creator: se envía al bot en execute_creator (ciclo / hora programada)
    creator_scheduled_time = db.Column(db.String(16), nullable=True)
    creator_timezone = db.Column(db.String(255), nullable=True)
    creator_cycle_time_minutes = db.Column(db.Integer, nullable=True)
    creator_time_config_type = db.Column(db.String(20), nullable=True)
    creator_accounts_per_cycle = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('bot_global_config', uselist=False))
