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
    
    def _make_request(self, method: str, endpoint: str, headers_override: Optional[Dict[str, str]] = None, return_response: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Make an authenticated request to the Contabo API.
        If return_response is True, returns a tuple (json_data, response_object).
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
        
        json_data = response.json()
        
        if return_response:
            return json_data, response
        return json_data
    
    def list_instances(self) -> List[Dict[str, Any]]:
        """
        List all compute instances from Contabo account.
        Handles pagination to get all instances.
        According to Contabo API docs, uses page (0-indexed) and size parameters.
        Returns a list of instance data.
        """
        all_instances = []
        page = 0  # Contabo API uses 0-indexed pages
        size = 100  # Máximo por página según documentación
        
        # Obtener primera página sin parámetros para ver estructura
        try:
            result, response_obj = self._make_request("GET", "compute/instances", return_response=True)
            data = result.get("data", [])
            all_instances.extend(data)
            
            # Verificar si hay información de paginación en la respuesta
            pagination = result.get("pagination", {})
            
            total_elements = pagination.get("totalElements") or pagination.get("total")
            total_pages = pagination.get("totalPages")
            
            # Si hay información de paginación explícita
            if total_pages and total_pages > 1:
                for p in range(1, total_pages):
                    params = {"page": p, "size": size}
                    try:
                        page_result = self._make_request("GET", "compute/instances", params=params)
                        page_data = page_result.get("data", [])
                        if page_data:
                            all_instances.extend(page_data)
                        else:
                            break
                    except Exception as e:
                        break
            # Si no hay info de paginación pero obtuvimos exactamente 10 (límite por defecto)
            elif len(data) == 10:
                # Intentar obtener más páginas - probar ambos formatos (0-indexed y 1-indexed)
                current_page_0 = 1  # Para 0-indexed, la siguiente página es 1
                current_page_1 = 1  # Para 1-indexed, la siguiente página es 1
                max_attempts = 100
                working_format = None
                
                while current_page_0 < max_attempts or current_page_1 < max_attempts:
                    found_more = False
                    
                    # Probar diferentes formatos de parámetros
                    param_formats = []
                    if working_format is None:
                        # Intentar todos los formatos posibles
                        param_formats = [
                            {"page": current_page_0, "size": size},  # 0-indexed
                            {"page": current_page_1, "size": size},  # 1-indexed (mismo valor, diferente interpretación)
                            {"pageNumber": current_page_1, "pageSize": size},
                            {"offset": current_page_1 * size, "limit": size},
                        ]
                    elif working_format == "page_0":
                        param_formats = [{"page": current_page_0, "size": size}]
                    elif working_format == "page_1":
                        param_formats = [{"page": current_page_1, "size": size}]
                    elif working_format == "pageNumber":
                        param_formats = [{"pageNumber": current_page_1, "pageSize": size}]
                    elif working_format == "offset":
                        param_formats = [{"offset": current_page_1 * size, "limit": size}]
                    
                    for params in param_formats:
                        try:
                            page_result = self._make_request("GET", "compute/instances", params=params)
                            page_data = page_result.get("data", [])
                            
                            if page_data:
                                all_instances.extend(page_data)
                                found_more = True
                                
                                # Identificar qué formato funciona
                                if working_format is None:
                                    if "page" in params:
                                        # Determinar si es 0-indexed o 1-indexed basándose en el valor
                                        if current_page_0 == 1 and params["page"] == 1:
                                            # Probamos page=1, si funciona puede ser 0-indexed o 1-indexed
                                            # Asumimos 0-indexed primero
                                            working_format = "page_0"
                                        else:
                                            working_format = "page_1"
                                    elif "pageNumber" in params:
                                        working_format = "pageNumber"
                                    elif "offset" in params:
                                        working_format = "offset"
                                
                                # Si obtuvimos menos de size, probablemente es la última página
                                if len(page_data) < size:
                                    return all_instances
                                break  # Este formato funciona
                        except Exception as e:
                            continue
                    
                    if not found_more:
                        break
                    
                    # Actualizar contadores según el formato que funciona
                    if working_format == "page_0":
                        current_page_0 += 1
                    elif working_format in ["page_1", "pageNumber", "offset"]:
                        current_page_1 += 1
        except Exception as e:
            if not all_instances:
                raise e
        
        return all_instances
    
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
    conflicts = 0  # VPS que existen pero pertenecen a otro usuario

    for instance in instances:
        instance_id = str(instance.get("instanceId"))
        
        # Check if already exists (globalmente, porque instance_id tiene restricción UNIQUE)
        existing_vps = VPS.query.filter_by(instance_id=instance_id).first()
        if existing_vps:
            # Si existe y es del mismo usuario, saltarlo
            if existing_vps.user_id == user_id:
                skipped += 1
            else:
                # Si existe pero es de otro usuario, es un conflicto (no debería pasar normalmente)
                conflicts += 1
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
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise
    
    result = {
        "added": added,
        "skipped": skipped,
        "total_from_contabo": len(instances),
    }
    
    if conflicts > 0:
        result["conflicts"] = conflicts
        result["warning"] = f"{conflicts} VPS ya existen pero pertenecen a otro usuario"
    
    return result
