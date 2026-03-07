import os
import requests
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv

from app.database import db
from app.models.vps import VPS

load_dotenv()


class ContaboService:
    """
    Service class for communicating with the Contabo API.
    Handles OAuth2 authentication and instance management.
    """
    
    BASE_URL = "https://api.contabo.com/v1"
    AUTH_URL = "https://auth.contabo.com/auth/realms/contabo/protocol/openid-connect/token"
    
    def __init__(self, client_id: str, client_secret: str, username: str, password: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self._access_token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
    
    def _get_access_token(self) -> str:
        """
        Get OAuth2 access token from Contabo.
        Caches the token until it expires.
        """
        # Check if we have a valid cached token
        if self._access_token and self._token_expires:
            if datetime.utcnow() < self._token_expires:
                return self._access_token
        
        # Request new token
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "username": self.username,
            "password": self.password,
            "grant_type": "password",
        }
        
        response = requests.post(self.AUTH_URL, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        self._access_token = token_data["access_token"]
        
        # Set expiration (with 60 second buffer)
        expires_in = token_data.get("expires_in", 300) - 60
        self._token_expires = datetime.utcnow() + timedelta(seconds=expires_in)
        
        return self._access_token
    
    def _make_request(self, method: str, endpoint: str, headers_override: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
        """
        Make an authenticated request to the Contabo API.
        """
        token = self._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "x-request-id": f"{uuid.uuid4()}",
            # "Content-Type": "application/json",
            # "x-trace-id": "" # implement when needed
        }
        
        if headers_override:
            headers.update(headers_override)
        
        url = f"{self.BASE_URL}/{endpoint}"
        response = requests.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        
        return response.json()
    
    def list_instances(self) -> List[Dict[str, Any]]:
        """
        List all compute instances from Contabo account.
        Returns a list of instance data.
        """
        result = self._make_request("GET", "compute/instances")
        return result.get("data", [])
    
    def restart_instance(self, instance_id: str) -> Dict[str, Any]:
        """
        Restart a specific compute instance.
        """
        result = self._make_request(
            "POST", 
            f"compute/instances/{instance_id}/actions/restart"
        )
        return result
    
    def get_instance(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific instance.
        """
        result = self._make_request("GET", f"compute/instances/{instance_id}")
        return result.get("data", [None])[0] if result.get("data") else None


def sync_instances_to_db(user_id: int, contabo_service: 'ContaboService') -> Dict[str, Any]:
    """
    Sync instances from Contabo to the local database.
    Only adds new instances, does not update existing ones.
    
    Returns: dict with counts of added and skipped instances
    """
    
    instances = contabo_service.list_instances()
    
    added = 0
    skipped = 0

    vps_instance_ids = [v[0] for v in VPS.query.with_entities(VPS.instance_id).filter_by(user_id=user_id).all()]
    
    for instance in instances:
        instance_id = str(instance.get("instanceId"))
        
        # Check if already exists
        if instance_id in vps_instance_ids:
            skipped += 1
            continue
        
        # Parse created date
        created_date = None
        if instance.get("createdDate"):
            try:
                created_date = datetime.fromisoformat(
                    instance["createdDate"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass
        
        # Get IP address (first IPv4 from ipConfig)
        ip_v4 = None
        ip_config = instance.get("ipConfig", {})
        v4_addresses = ip_config.get("v4", {}).get("ip", [])
        if v4_addresses:
            ip_v4 = v4_addresses[0] if isinstance(v4_addresses, list) else v4_addresses
        
        # Create new VPS record
        new_vps = VPS(
            user_id=user_id,
            contabo_name=instance.get("name"),
            display_name=instance.get("displayName"),
            instance_id=instance_id,
            ip_v4=ip_v4,
            mac_address=instance.get("macAddress"),
            ram_mb=instance.get("ramMb"),
            cpu_cores=instance.get("cpuCores"),
            disk_mb=instance.get("diskMb"),
            os_type=instance.get("osType"),
            status=instance.get("status"),
            product_name=instance.get("productName"),
            data_center=instance.get("dataCenter"),
            region=instance.get("region"),
            imagen_id=str(instance.get("imageId")) if instance.get("imageId") else None,
            created_date=created_date,
        )
        
        db.session.add(new_vps)
        added += 1
    
    db.session.commit()
    
    return {
        "added": added,
        "skipped": skipped,
        "total_from_contabo": len(instances),
    }
