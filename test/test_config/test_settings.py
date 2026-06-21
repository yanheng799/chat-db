import os
import pytest

from config.settings import Settings


class TestSettings:
    """Test pydantic-settings reads configuration from environment."""

    def test_reads_encryption_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", "test-fernet-key-value")
        s = Settings()
        assert s.encryption_key == "test-fernet-key-value"

    def test_reads_sync_interval_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("METADATA_SYNC_INTERVAL_HOURS", "12")
        s = Settings()
        assert s.metadata_sync_interval_hours == 12

    def test_default_sync_interval_is_24(self) -> None:
        s = Settings()
        assert s.metadata_sync_interval_hours == 24

    def test_default_encryption_key_is_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        s = Settings(_env_file=None)  # don't fall through to .env
        assert s.encryption_key == ""

    def test_reads_postgres_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POSTGRES_HOST", "db.example.com")
        monkeypatch.setenv("POSTGRES_PORT", "5433")
        monkeypatch.setenv("POSTGRES_USER", "admin")
        monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
        monkeypatch.setenv("POSTGRES_DB", "mydb")
        s = Settings()
        assert s.postgres_host == "db.example.com"
        assert s.postgres_port == 5433
        assert s.postgres_user == "admin"
        assert s.postgres_password == "secret"
        assert s.postgres_db == "mydb"
