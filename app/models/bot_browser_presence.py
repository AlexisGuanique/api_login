from datetime import datetime
from app.database import db


class BotBrowserPresence(db.Model):
    """Navegadores disponibles reportados por cada bot."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bot_id = db.Column(db.Integer, db.ForeignKey('bot.id'), nullable=False)
    browser_name = db.Column(db.String(100), nullable=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('bot_id', 'browser_name', name='uq_bot_browser_presence'),
        db.Index('idx_bot_browser_presence_user_id', 'user_id'),
        db.Index('idx_bot_browser_presence_bot_id', 'bot_id'),
    )
