import pytest
from httpx import AsyncClient


class TestManualSync:
    async def test_sync_returns_202(
        self, client: AsyncClient, fernet_key: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
        r = await client.post(
            "/api/datasources",
            json={
                "name": "sync-test", "engine": "postgresql",
                "host": "127.0.0.1", "port": 5432, "username": "u",
                "password": "p", "database": "d",
            },
        )
        ds_id = r.json()["id"]
        resp = await client.post(f"/api/datasources/{ds_id}/sync")
        assert resp.status_code == 202
        assert "sync_log_id" in resp.json()

    async def test_sync_with_table_scope(
        self, client: AsyncClient, fernet_key: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
        r = await client.post(
            "/api/datasources",
            json={
                "name": "sync-scope", "engine": "postgresql",
                "host": "127.0.0.1", "port": 5432, "username": "u",
                "password": "p", "database": "d",
            },
        )
        ds_id = r.json()["id"]
        resp = await client.post(
            f"/api/datasources/{ds_id}/sync",
            json={"table_scope": [{"schema": "public", "table": "orders"}]},
        )
        assert resp.status_code == 202

    async def test_concurrent_sync_returns_409(
        self, client: AsyncClient, fernet_key: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
        r = await client.post(
            "/api/datasources",
            json={
                "name": "sync-409", "engine": "postgresql",
                "host": "127.0.0.1", "port": 5432, "username": "u",
                "password": "p", "database": "d",
            },
        )
        ds_id = r.json()["id"]
        # First sync accepted
        await client.post(f"/api/datasources/{ds_id}/sync")
        # Second sync should be 409 (first still running)
        resp = await client.post(f"/api/datasources/{ds_id}/sync")
        assert resp.status_code == 409

    async def test_sync_nonexistent_returns_404(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/datasources/00000000-0000-0000-0000-000000000000/sync"
        )
        assert resp.status_code == 404
