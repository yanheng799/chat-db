import pytest

from config.encryption import generate_fernet_key


@pytest.fixture()
def fernet_key() -> str:
    return generate_fernet_key()
