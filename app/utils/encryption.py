"""Fernet symmetric encryption for secrets stored at rest."""

import os
from cryptography.fernet import Fernet

_KEY = None


def _get_fernet():
    global _KEY
    if _KEY is None:
        raw = os.environ.get("FERNET_KEY", "")
        if not raw:
            raise RuntimeError("FERNET_KEY environment variable is not set")
        _KEY = Fernet(raw.encode() if isinstance(raw, str) else raw)
    return _KEY


def encrypt(plaintext):
    """Encrypt a string and return the URL-safe base64 ciphertext."""
    if not plaintext:
        return None
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext):
    """Decrypt a URL-safe base64 ciphertext back to a string."""
    if not ciphertext:
        return None
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except Exception:
        return ciphertext


def generate_key():
    """Generate a new Fernet key (for initial setup)."""
    return Fernet.generate_key().decode()
