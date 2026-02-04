from datetime import datetime
import enum
from app.database import db


class ProxyKind(enum.Enum):
    DATAIMPULSE = "Dataimpulse"
    UNKNOWN = "unknown"


class Proxy(db.Model):
    __tablename__ = 'proxies'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    host = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    kind = db.Column(db.Enum(ProxyKind), default=ProxyKind.UNKNOWN, nullable=False)
    username = db.Column(db.String(255), nullable=True)
    password = db.Column(db.String(500), nullable=True) # Encrypted, needs space
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relación con usuario
    user = db.relationship("User", backref=db.backref("proxies", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "is_active": self.is_active,
            "kind": self.kind.value,
            "username": self.username,
            # Password no se devuelve por seguridad
            "created_at": self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            "updated_at": self.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        }
