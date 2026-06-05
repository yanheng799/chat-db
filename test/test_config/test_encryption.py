import pytest

from config.encryption import decrypt_value, encrypt_value


class TestEncryption:
    """Test Fernet-based encrypt/decrypt utility for data source passwords."""

    def test_encrypt_decrypt_roundtrip(self, fernet_key: str) -> None:
        plaintext = "my_secret_password"
        encrypted = encrypt_value(plaintext, fernet_key)
        assert encrypted != plaintext
        assert decrypt_value(encrypted, fernet_key) == plaintext

    def test_different_inputs_produce_different_ciphertext(
        self, fernet_key: str
    ) -> None:
        encrypted_a = encrypt_value("password_a", fernet_key)
        encrypted_b = encrypt_value("password_b", fernet_key)
        assert encrypted_a != encrypted_b

    def test_same_input_produces_different_ciphertext_each_time(
        self, fernet_key: str
    ) -> None:
        plaintext = "same_password"
        encrypted_1 = encrypt_value(plaintext, fernet_key)
        encrypted_2 = encrypt_value(plaintext, fernet_key)
        # Fernet uses timestamp + IV, so same input -> different ciphertext
        assert encrypted_1 != encrypted_2
        assert decrypt_value(encrypted_1, fernet_key) == plaintext
        assert decrypt_value(encrypted_2, fernet_key) == plaintext

    def test_decrypt_with_wrong_key_raises_error(
        self, fernet_key: str
    ) -> None:
        from cryptography.fernet import Fernet

        wrong_key = Fernet.generate_key().decode()
        encrypted = encrypt_value("secret", fernet_key)
        with pytest.raises(Exception):
            decrypt_value(encrypted, wrong_key)

    def test_decrypt_invalid_token_raises_error(self, fernet_key: str) -> None:
        with pytest.raises(Exception):
            decrypt_value("not-a-valid-fernet-token", fernet_key)

    def test_encrypt_empty_string(self, fernet_key: str) -> None:
        encrypted = encrypt_value("", fernet_key)
        assert decrypt_value(encrypted, fernet_key) == ""

    def test_encrypt_unicode_password(self, fernet_key: str) -> None:
        plaintext = "密码123!@#"
        encrypted = encrypt_value(plaintext, fernet_key)
        assert decrypt_value(encrypted, fernet_key) == plaintext

    def test_generate_fernet_key(self) -> None:
        from config.encryption import generate_fernet_key

        key = generate_fernet_key()
        assert isinstance(key, str)
        assert len(key) > 0
        # Fernet keys are base64-encoded 32-byte keys
        assert encrypt_value("test", key) is not None
