import base64
import hashlib
from cryptography.fernet import Fernet
from app.core.config import settings

def _get_fernet() -> Fernet:
    key = hashlib.sha256(settings.encryption_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))

def encrypt(plaintext: str) -> str:
    if not plaintext:
        return plaintext
    return _get_fernet().encrypt(plaintext.encode()).decode()

def decrypt(ciphertext: str) -> str:
    if not ciphertext:
        return ciphertext
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except Exception:
        return ciphertext

MASKED = "********"

def mask(value: str) -> str:
    return MASKED if value else value

def is_masked(value: str) -> bool:
    return value == MASKED
