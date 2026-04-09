import base64
import hashlib
import logging
from cryptography.fernet import Fernet
from app.core.config import settings

logger = logging.getLogger(__name__)

def _get_fernet() -> Fernet:
    key = hashlib.sha256(settings.encryption_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))

def encrypt(plaintext: str) -> str:
    if not plaintext:
        return plaintext
    return _get_fernet().encrypt(plaintext.encode()).decode()


class DecryptionError(Exception):
    """Raised when a stored password cannot be decrypted."""


def decrypt(ciphertext: str) -> str:
    if not ciphertext:
        return ciphertext
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except Exception as exc:
        logger.error("Failed to decrypt value (wrong key or corrupted data): %s", exc)
        raise DecryptionError(
            "Could not decrypt stored password. "
            "The encryption key may have changed — please re-enter the password."
        ) from exc

MASKED = "********"

def mask(value: str) -> str:
    return MASKED if value else value

def is_masked(value: str) -> bool:
    return value == MASKED
