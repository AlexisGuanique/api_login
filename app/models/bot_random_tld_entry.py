from datetime import datetime
from app.database import db


class BotRandomTldEntry(db.Model):
    """Terminaciones para dominios aleatorios por usuario."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tld = db.Column(db.String(64), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'tld', name='uq_user_random_tld_entry'),
        db.Index('idx_bot_random_tld_entry_user_id', 'user_id'),
    )
