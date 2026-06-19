import base64
from cryptography.fernet import Fernet, InvalidToken


def generate_fernet_key() -> str:
    return Fernet.generate_key().decode()


def _validate_key(key: str) -> None:
    """Raise a clear error if the key is not a valid Fernet key."""
    try:
        raw = base64.urlsafe_b64decode(key.encode())
    except Exception as e:
        raise ValueError(
            f"ENCRYPTION_KEY is not valid base64. "
            f"Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        ) from e
    if len(raw) != 32:
        raise ValueError(
            f"ENCRYPTION_KEY must decode to 32 bytes, got {len(raw)}. "
            f"Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )


def encrypt_value(plaintext: str, key: str) -> str:
    _validate_key(key)
    fernet = Fernet(key.encode())
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str, key: str) -> str:
    _validate_key(key)
    fernet = Fernet(key.encode())
    try:
        return fernet.decrypt(ciphertext.encode()).decode()
    except Exception as exc:
        if isinstance(exc, InvalidToken):
            raise ValueError("Failed to decrypt: invalid token or wrong key") from exc
        raise
