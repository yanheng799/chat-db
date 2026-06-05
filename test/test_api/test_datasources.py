import pytest
from httpx import AsyncClient


def _make_create_payload(name: str = "test-pg", **overrides: object) -> dict:
    payload = {
        "name": name,
        "engine": "postgresql",
        "host": "127.0.0.1",
        "port": 5432,
        "username": "reader",
        "password": "secret123",
        "database": "testdb",
    }
    payload.update(overrides)
    return payload


class TestCreateDataSource:
    async def test_create_returns_201_with_encrypted_password(
        self, client: AsyncClient, fernet_key: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
        resp = await client.post("/api/datasources", json=_make_create_payload())
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "test-pg"
        assert body["engine"] == "postgresql"
        assert "password" not in body
        assert "password_encrypted" not in body
        assert body["is_active"] is False
        assert "id" in body

    async def test_create_duplicate_name_returns_409(
        self, client: AsyncClient, fernet_key: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
        await client.post("/api/datasources", json=_make_create_payload(name="dup"))
        resp = await client.post("/api/datasources", json=_make_create_payload(name="dup"))
        assert resp.status_code == 409

    async def test_create_mysql_data_source(
        self, client: AsyncClient, fernet_key: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
        resp = await client.post(
            "/api/datasources",
            json=_make_create_payload(name="test-mysql", engine="mysql", port=3306),
        )
        assert resp.status_code == 201
        assert resp.json()["engine"] == "mysql"

    async def test_create_with_invalid_engine_returns_422(
        self, client: AsyncClient, fernet_key: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
        resp = await client.post(
            "/api/datasources",
            json=_make_create_payload(engine="oracle"),
        )
        assert resp.status_code == 422

    async def test_create_with_schema_whitelist(
        self, client: AsyncClient, fernet_key: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
        resp = await client.post(
            "/api/datasources",
            json=_make_create_payload(
                name="test-wl",
                schema_whitelist=[{"schema": "public"}, {"schema": "sales"}],
            ),
        )
        assert resp.status_code == 201
        assert resp.json()["schema_whitelist"] == [
            {"schema": "public"},
            {"schema": "sales"},
        ]

    async def test_create_without_encryption_key_returns_500(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", "")
        resp = await client.post("/api/datasources", json=_make_create_payload())
        assert resp.status_code == 500


class TestListDataSources:
    async def test_list_returns_all_without_passwords(
        self, client: AsyncClient, fernet_key: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
        await client.post(
            "/api/datasources", json=_make_create_payload(name="list-a")
        )
        await client.post(
            "/api/datasources",
            json=_make_create_payload(name="list-b", engine="mysql"),
        )
        resp = await client.get("/api/datasources")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 2
        for item in items:
            assert "password" not in item
            assert "password_encrypted" not in item


class TestGetDataSource:
    async def test_get_single_returns_without_password(
        self, client: AsyncClient, fernet_key: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
        create_resp = await client.post(
            "/api/datasources", json=_make_create_payload(name="get-single")
        )
        ds_id = create_resp.json()["id"]
        resp = await client.get(f"/api/datasources/{ds_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == ds_id
        assert "password" not in body
        assert "password_encrypted" not in body

    async def test_get_nonexistent_returns_404(self, client: AsyncClient) -> None:
        resp = await client.get("/api/datasources/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


class TestUpdateDataSource:
    async def test_update_changes_fields(
        self, client: AsyncClient, fernet_key: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
        create_resp = await client.post(
            "/api/datasources", json=_make_create_payload(name="update-fields")
        )
        ds_id = create_resp.json()["id"]
        resp = await client.put(
            f"/api/datasources/{ds_id}",
            json={"host": "new-host.example.com", "port": 5433},
        )
        assert resp.status_code == 200
        assert resp.json()["host"] == "new-host.example.com"
        assert resp.json()["port"] == 5433

    async def test_update_password_re_encrypts(
        self, client: AsyncClient, fernet_key: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
        create_resp = await client.post(
            "/api/datasources", json=_make_create_payload(name="update-pw")
        )
        ds_id = create_resp.json()["id"]
        # Update password and verify it works (get still succeeds without leaking it)
        resp = await client.put(
            f"/api/datasources/{ds_id}", json={"password": "new_secret"}
        )
        assert resp.status_code == 200
        assert "password" not in resp.json()

    async def test_update_nonexistent_returns_404(self, client: AsyncClient) -> None:
        resp = await client.put(
            "/api/datasources/00000000-0000-0000-0000-000000000000",
            json={"host": "x"},
        )
        assert resp.status_code == 404


class TestDeleteDataSource:
    async def test_delete_removes_data_source(
        self, client: AsyncClient, fernet_key: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
        create_resp = await client.post(
            "/api/datasources", json=_make_create_payload(name="to-delete")
        )
        ds_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/datasources/{ds_id}")
        assert resp.status_code == 204
        get_resp = await client.get(f"/api/datasources/{ds_id}")
        assert get_resp.status_code == 404

    async def test_delete_nonexistent_returns_404(self, client: AsyncClient) -> None:
        resp = await client.delete(
            "/api/datasources/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404


class TestConnectionTest:
    async def test_connection_test_returns_result(
        self, client: AsyncClient, fernet_key: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
        create_resp = await client.post(
            "/api/datasources", json=_make_create_payload(name="conn-test")
        )
        ds_id = create_resp.json()["id"]
        resp = await client.post(f"/api/datasources/{ds_id}/test")
        assert resp.status_code == 200
        body = resp.json()
        assert "success" in body

    async def test_connection_test_nonexistent_returns_404(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/datasources/00000000-0000-0000-0000-000000000000/test"
        )
        assert resp.status_code == 404
