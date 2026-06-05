from cryptography.fernet import Fernet, InvalidToken


def generate_fernet_key() -> str:
    return Fernet.generate_key().decode()


def encrypt_value(plaintext: str, key: str) -> str:
    fernet = Fernet(key.encode())
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str, key: str) -> str:
    fernet = Fernet(key.encode())
    try:
        return fernet.decrypt(ciphertext.encode()).decode()
    except Exception as exc:
        if isinstance(exc, InvalidToken):
            raise ValueError("Failed to decrypt: invalid token or wrong key") from exc
        raise
