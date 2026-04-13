from datetime import datetime
from app.database import db


class BotDomainEntry(db.Model):
    """Dominios configurados por usuario para modo no-33mail."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    domain = db.Column(db.String(255), nullable=False)
    fill_domain = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'domain', name='uq_user_domain_entry'),
        db.Index('idx_bot_domain_entry_user_id', 'user_id'),
    )
