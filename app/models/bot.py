from datetime import datetime
from app.database import db


class Bot(db.Model):
    """Modelo para representar bots conectados al sistema"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # Nombre identificador del bot
    bot_type = db.Column(db.String(20), nullable=False)  # 'creador' o 'logueador'
    status = db.Column(db.String(20), default='offline', nullable=False)  # 'online', 'offline', 'running', 'stopped'
    socket_id = db.Column(db.String(100), nullable=True)  # ID de conexión WebSocket
    next_cycle_at = db.Column(db.DateTime, nullable=True)  # Hora estimada del próximo ciclo (solo para logueadores)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relación con User
    user = db.relationship('User', backref=db.backref('bots', lazy=True))
    
    # Índices
    __table_args__ = (
        db.Index('idx_bot_user_id', 'user_id'),
        db.Index('idx_bot_status', 'status'),
        db.Index('idx_bot_socket_id', 'socket_id'),
    )
    
    def __repr__(self):
        return f'<Bot {self.name} ({self.bot_type})>'
    
    def to_dict(self):
        # Si no hay socket_id (None o cadena vacía), el bot está offline independientemente del estado guardado
        # Un bot solo puede estar 'stopped', 'running' u 'online' si tiene una conexión WebSocket activa
        
        # Verificar si el bot tiene conexión WebSocket activa de forma robusta
        socket_id_str = str(self.socket_id) if self.socket_id is not None else ''
        has_connection = bool(socket_id_str.strip())
        
        # Si no hay conexión, siempre mostrar como offline
        if not has_connection:
            effective_status = 'offline'
        else:
            # Si hay conexión, usar el estado guardado (stopped, running, online)
            effective_status = self.status
        
        # Función helper para convertir datetime a ISO con 'Z' (UTC)
        def to_iso_utc(dt):
            if not dt:
                return None
            iso_str = dt.isoformat()
            # Si no termina en 'Z' ni tiene offset de timezone, agregar 'Z' para indicar UTC
            if not iso_str.endswith('Z') and '+' not in iso_str and '-' not in iso_str[-6:]:
                iso_str += 'Z'
            return iso_str
        
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'bot_type': self.bot_type,
            'status': effective_status,
            'socket_id': self.socket_id,
            'next_cycle_at': to_iso_utc(self.next_cycle_at),
            'last_seen': to_iso_utc(self.last_seen),
            'created_at': to_iso_utc(self.created_at),
            'updated_at': to_iso_utc(self.updated_at),
        }

