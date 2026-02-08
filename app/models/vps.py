from datetime import datetime
from app.database import db


class VPS(db.Model):
    __tablename__ = 'vps'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Contabo instance info
    contabo_name = db.Column(db.String(255), nullable=True)
    display_name = db.Column(db.String(255), nullable=True)
    instance_id = db.Column(db.String(100), unique=True, nullable=False)
    
    # Network
    ip_v4 = db.Column(db.String(45), nullable=True)
    mac_address = db.Column(db.String(17), nullable=True)
    
    # Hardware specs
    ram_mb = db.Column(db.Integer, nullable=True)
    cpu_cores = db.Column(db.Integer, nullable=True)
    disk_mb = db.Column(db.Integer, nullable=True)
    
    # System info
    os_type = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), nullable=True)
    product_name = db.Column(db.String(255), nullable=True)
    
    # Location
    data_center = db.Column(db.String(100), nullable=True)
    region = db.Column(db.String(100), nullable=True)
    
    # Image
    imagen_id = db.Column(db.String(100), nullable=True)
    
    # Dates
    created_date = db.Column(db.DateTime, nullable=True)  # Creation date in Contabo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = db.relationship("User", backref=db.backref("vps_instances", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "contabo_name": self.contabo_name,
            "display_name": self.display_name,
            "instance_id": self.instance_id,
            "ip_v4": self.ip_v4,
            "mac_address": self.mac_address,
            "ram_mb": self.ram_mb,
            "cpu_cores": self.cpu_cores,
            "disk_mb": self.disk_mb,
            "os_type": self.os_type,
            "status": self.status,
            "product_name": self.product_name,
            "data_center": self.data_center,
            "region": self.region,
            "imagen_id": self.imagen_id,
            "created_date": self.created_date.strftime('%Y-%m-%d %H:%M:%S') if self.created_date else None,
            "created_at": self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            "updated_at": self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
        }
