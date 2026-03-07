from datetime import datetime
from app.database import db


class ContaboConfig(db.Model):
    __tablename__ = 'contabo_config'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    
    # Contabo API credentials
    client_id = db.Column(db.String(255), nullable=False)
    client_secret = db.Column(db.Text, nullable=False)  # Encrypted with Fernet
    username = db.Column(db.String(255), nullable=False)
    password = db.Column(db.Text, nullable=False)  # Encrypted with Fernet
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # One-to-one relationship with User
    user = db.relationship("User", backref=db.backref("contabo_config", uselist=False))

    def to_dict(self, include_sensitive=False):
        """
        Return dict representation.
        By default, sensitive fields (client_secret, password) are excluded.
        """
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "client_id": self.client_id,
            "username": self.username,
            "created_at": self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            "updated_at": self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
        }
        if include_sensitive:
            data["client_secret"] = self.client_secret
            data["password"] = self.password
        return data
