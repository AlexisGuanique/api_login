from datetime import datetime
from app.database import db

class Email(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relación con User - Muchos emails pertenecen a un usuario
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('emails', lazy=True))
    
    # Índices para optimizar consultas frecuentes
    __table_args__ = (
        db.Index('idx_email_user_created', 'user_id', 'created_at'),  # Para consultas FIFO por usuario
        db.Index('idx_email_user_id', 'user_id'),  # Para consultas por usuario
        db.Index('idx_email_created', 'created_at'),  # Para ordenamiento por fecha
    )
    
    def __repr__(self):
        return f'<Email {self.email}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'user_id': self.user_id
        }