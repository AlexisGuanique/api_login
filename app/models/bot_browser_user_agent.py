from datetime import datetime
from app.database import db


class BotBrowserUserAgent(db.Model):
    """Configuración de User-Agent por navegador (a nivel usuario)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    browser_name = db.Column(db.String(100), nullable=False)
    user_agent = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'browser_name', name='uq_user_browser_user_agent'),
        db.Index('idx_bot_browser_user_agent_user_id', 'user_id'),
    )
