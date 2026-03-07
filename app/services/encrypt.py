import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import base64

load_dotenv()

class EncryptionService:
    def __init__(self):
        # Intentar obtener la key del env
        key = os.getenv('PROXY_SECRET_KEY')
        if not key:
            # Si no hay key, intentar generar una basada en SECRET_KEY o usar una por defecto (Inseguro para prod)
            # Para Fernet, la key debe ser 32 url-safe base64-encoded bytes.
            app_secret = os.getenv('SECRET_KEY', 'my_very_secret_key_needs_to_be_32_bytes_long!!')
            # Ajustar a 32 bytes y codificar
            key_bytes = app_secret.ljust(32)[:32].encode()
            key = base64.urlsafe_b64encode(key_bytes).decode()
            
        self.fernet = Fernet(key)

    def encrypt(self, data: str) -> str:
        if not data:
            return None
        return self.fernet.encrypt(data.encode()).decode()

    def decrypt(self, data: str) -> str:
        if not data:
            return None
        try:
            return self.fernet.decrypt(data.encode()).decode()
        except:
            return None

encrypt_service = EncryptionService()
