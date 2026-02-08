import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import base64

load_dotenv()


class ContaboEncryptionService:
    """
    Encryption service for Contabo credentials.
    Uses a separate key from proxy encryption for security isolation.
    """
    def __init__(self):
        key = os.getenv('CONTABO_SECRET_KEY')
        if not key:
            # Fallback: derive from SECRET_KEY (not recommended for production)
            app_secret = os.getenv('SECRET_KEY', 'contabo_default_key_needs_32_bytes!!')
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
        except Exception:
            return None


contabo_encrypt_service = ContaboEncryptionService()
