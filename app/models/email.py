from datetime import datetime
from app.database import db

class Email(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False)  # Ahora almacena solo el dominio (ej: @accept493zyka.33mail.com)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Contador de usos del email (0 = nunca usado, 1 = usado una vez, 2 = usado dos veces)
    usage_count = db.Column(db.Integer, default=0, nullable=False)
    
    # Estado del email: 'active' (activo), 'completed' (completado), 'deleted' (eliminado)
    status = db.Column(db.String(20), default='active', nullable=False)
    
    # Relación con User - Muchos emails pertenecen a un usuario
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('emails', lazy=True))
    
    # Índices para optimizar consultas frecuentes
    __table_args__ = (
        db.Index('idx_email_user_status_usage_created', 'user_id', 'status', 'usage_count', 'created_at'),  # Para consultas FIFO por usuario, estado y uso
        db.Index('idx_email_user_id', 'user_id'),  # Para consultas por usuario
        db.Index('idx_email_status', 'status'),  # Para consultas por estado
        db.Index('idx_email_usage_count', 'usage_count'),  # Para consultas por uso
        db.Index('idx_email_created', 'created_at'),  # Para ordenamiento por fecha
    )
    
    def __repr__(self):
        return f'<Email {self.email}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'user_id': self.user_id,
            'usage_count': self.usage_count,
            'status': self.status
        }