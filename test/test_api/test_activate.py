import pytest
from httpx import AsyncClient


class TestActivateDataSource:
    async def test_activate_returns_200_and_sets_is_active(
        self, client: AsyncClient, fernet_key: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
        create_resp = await client.post(
            "/api/datasources",
            json={
                "name": "activate-test",
                "engine": "postgresql",
                "host": "127.0.0.1",
                "port": 5432,
                "username": "reader",
                "password": "secret",
                "database": "testdb",
            },
        )
        ds_id = create_resp.json()["id"]
        resp = await client.post(f"/api/datasources/{ds_id}/activate")
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_active"] is True

    async def test_activate_deactivates_previous(
        self, client: AsyncClient, fernet_key: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
        # Create two data sources
        r1 = await client.post(
            "/api/datasources",
            json={
                "name": "ds-a",
                "engine": "postgresql",
                "host": "127.0.0.1",
                "port": 5432,
                "username": "u",
                "password": "p",
                "database": "d",
            },
        )
        r2 = await client.post(
            "/api/datasources",
            json={
                "name": "ds-b",
                "engine": "postgresql",
                "host": "127.0.0.1",
                "port": 5432,
                "username": "u",
                "password": "p",
                "database": "d",
            },
        )
        id_a = r1.json()["id"]
        id_b = r2.json()["id"]

        # Activate A
        await client.post(f"/api/datasources/{id_a}/activate")
        # Activate B — should deactivate A
        await client.post(f"/api/datasources/{id_b}/activate")

        # Check A is inactive
        get_a = await client.get(f"/api/datasources/{id_a}")
        assert get_a.json()["is_active"] is False
        # Check B is active
        get_b = await client.get(f"/api/datasources/{id_b}")
        assert get_b.json()["is_active"] is True

    async def test_activate_nonexistent_returns_404(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/datasources/00000000-0000-0000-0000-000000000000/activate"
        )
        assert resp.status_code == 404

    async def test_deactivate_returns_200(
        self, client: AsyncClient, fernet_key: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
        r = await client.post(
            "/api/datasources",
            json={
                "name": "deact-test",
                "engine": "postgresql",
                "host": "127.0.0.1",
                "port": 5432,
                "username": "u",
                "password": "p",
                "database": "d",
            },
        )
        ds_id = r.json()["id"]
        await client.post(f"/api/datasources/{ds_id}/activate")
        resp = await client.post(f"/api/datasources/{ds_id}/deactivate")
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False


class TestMetadataOverview:
    async def test_metadata_overview_returns_counts(
        self, client: AsyncClient, fernet_key: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
        r = await client.post(
            "/api/datasources",
            json={
                "name": "meta-test",
                "engine": "postgresql",
                "host": "127.0.0.1",
                "port": 5432,
                "username": "u",
                "password": "p",
                "database": "d",
            },
        )
        ds_id = r.json()["id"]
        resp = await client.get(f"/api/datasources/{ds_id}/metadata")
        assert resp.status_code == 200
        body = resp.json()
        assert "table_count" in body
        assert "column_count" in body


class TestSyncLogs:
    async def test_sync_logs_returns_list(
        self, client: AsyncClient, fernet_key: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
        r = await client.post(
            "/api/datasources",
            json={
                "name": "sync-log-test",
                "engine": "postgresql",
                "host": "127.0.0.1",
                "port": 5432,
                "username": "u",
                "password": "p",
                "database": "d",
            },
        )
        ds_id = r.json()["id"]
        resp = await client.get(f"/api/datasources/{ds_id}/sync-logs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
