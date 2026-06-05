import uuid

import pytest


@pytest.fixture()
def sample_pg_config() -> dict:
    return {
        "id": str(uuid.uuid4()),
        "engine": "postgresql",
        "host": "127.0.0.1",
        "port": 5432,
        "username": "reader",
        "password": "secret",
        "database": "testdb",
    }


@pytest.fixture()
def connection_manager():
    from db.connection import ConnectionManager

    return ConnectionManager()
