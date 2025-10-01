from datetime import datetime
from app.database import db

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_agent = db.Column(db.Text, nullable=False)
    email = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    cookie = db.Column(db.Text, nullable=False)  # JSON string para almacenar las cookies
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relación con User - Muchas cuentas pueden pertenecer a un usuario
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('accounts', lazy=True))
    
    # Índices para optimizar consultas frecuentes
    __table_args__ = (
        db.Index('idx_account_user_created', 'user_id', 'created_at'),  # Para consultas por usuario y fecha
        db.Index('idx_account_user_id', 'user_id'),  # Para consultas por usuario
        db.Index('idx_account_email', 'email'),  # Para búsquedas por email
        db.Index('idx_account_created', 'created_at'),  # Para ordenamiento por fecha
    )
    
    def __repr__(self):
        return f'<Account {self.email}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_agent': self.user_agent,
            'email': self.email,
            'password': self.password,
            'cookie': self.cookie,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'user_id': self.user_id
        }
