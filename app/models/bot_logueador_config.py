from datetime import datetime
from app.database import db


class BotLogueadorConfig(db.Model):
    """Configuración global del bot logueador por usuario."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)

    # Ciclo normal
    iterations = db.Column(db.Integer, nullable=False, default=16)
    interval_seconds = db.Column(db.Integer, nullable=False, default=7200)
    user_agent = db.Column(db.Text, nullable=True, default="")

    # Credenciales Ultra
    ultra_email = db.Column(db.String(255), nullable=True)
    ultra_password = db.Column(db.String(255), nullable=True)

    # Modo de ejecución / origen de cuentas
    use_local_accounts = db.Column(db.Boolean, nullable=False, default=False)
    ultra_login_mode = db.Column(db.String(20), nullable=False, default="sqlite")
    run_repetidas = db.Column(db.Boolean, nullable=False, default=False)

    # Configuración repetidas
    accounts_to_repeat = db.Column(db.Integer, nullable=False, default=5)
    repetitions_count = db.Column(db.Integer, nullable=False, default=3)
    repetidas_interval_seconds = db.Column(db.Integer, nullable=False, default=7200)
    partitions_count = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('bot_logueador_config', uselist=False))

    def to_payload(self) -> dict:
        """Formato enviado al bot logueador para sincronizar configuración."""
        return {
            "iterations": int(self.iterations or 16),
            "interval_seconds": int(self.interval_seconds or 7200),
            "user_agent": (self.user_agent or "").strip(),
            "ultra_email": (self.ultra_email or "").strip() or None,
            "ultra_password": (self.ultra_password or "").strip() or None,
            "use_local_accounts": bool(self.use_local_accounts),
            "ultra_login_mode": "ui" if (self.ultra_login_mode or "").strip().lower() == "ui" else "sqlite",
            "run_repetidas": bool(self.run_repetidas),
            "accounts_to_repeat": max(1, int(self.accounts_to_repeat or 5)),
            "repetitions_count": max(1, int(self.repetitions_count or 3)),
            "repetidas_interval_seconds": max(1, int(self.repetidas_interval_seconds or 7200)),
            "partitions_count": max(1, int(self.partitions_count or 1)),
        }
