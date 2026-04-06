"""Fernet encryption/decryption for tenant API keys stored in the database."""

from cryptography.fernet import Fernet

from app.config import settings


def _fernet() -> Fernet:
    return Fernet(settings.encryption_key.encode())


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string; returns a URL-safe base64 token."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted token back to plaintext."""
    return _fernet().decrypt(ciphertext.encode()).decode()
