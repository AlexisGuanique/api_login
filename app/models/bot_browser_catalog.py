from datetime import datetime
from app.database import db


class BotBrowserCatalog(db.Model):
    """Catálogo de navegadores reportados por los bots del usuario."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    browser_name = db.Column(db.String(100), nullable=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('bot_browser_catalog', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'browser_name', name='uq_user_browser_name'),
        db.Index('idx_bot_browser_catalog_user_id', 'user_id'),
    )
