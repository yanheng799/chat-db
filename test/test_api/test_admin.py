"""Behavior tests for admin API endpoints — via public HTTP interface (Phase 10 TDD)."""

import uuid

import pytest
from httpx import AsyncClient


class TestAdminSync:
    @pytest.mark.asyncio
    async def test_sync_status_returns_valid_response(self, client: AsyncClient):
        r = await client.get("/api/admin/sync/status")
        assert r.status_code == 200
        data = r.json()
        assert "latest" in data and "status" in data

    @pytest.mark.asyncio
    async def test_sync_logs_returns_list(self, client: AsyncClient):
        r = await client.get("/api/admin/sync/logs?limit=5")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data["logs"], list)


class TestAdminGraph:
    @pytest.mark.asyncio
    async def test_graph_nodes_returns_counts(self, client: AsyncClient):
        r = await client.get("/api/admin/graph/nodes/test-ds-id")
        assert r.status_code == 200
        data = r.json()
        assert "tables" in data and "columns" in data

    @pytest.mark.asyncio
    async def test_graph_edges_returns_list(self, client: AsyncClient):
        r = await client.get("/api/admin/graph/edges/test-ds-id")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data["edges"], list)


class TestAdminMappings:
    async def _create_ds(self, db_session):
        from config.data_source_model import DataSource
        from config.encryption import encrypt_value, generate_fernet_key
        ds_id = uuid.uuid4()
        key = generate_fernet_key()
        db_session.add(DataSource(
            id=ds_id, name=f"admin-test-{ds_id.hex[:6]}", engine="postgresql",
            host="localhost", port=5432, username="test",
            password_encrypted=encrypt_value("test", key), database="testdb",
        ))
        await db_session.commit()
        return str(ds_id)

    @pytest.mark.asyncio
    async def test_enum_mapping_crud_roundtrip(self, client: AsyncClient, db_session):
        ds_id = await self._create_ds(db_session)
        r = await client.post("/api/admin/mappings/enum", json={
            "data_source_id": ds_id, "table_name": "t", "column_name": "c",
            "value": "completed", "display": "已完成", "aliases": ["完结"]
        })
        assert r.status_code == 200
        r = await client.get(f"/api/admin/mappings/enum?data_source_id={ds_id}")
        assert r.status_code == 200
        items = r.json()["items"]
        assert any(it.get("value") == "completed" for it in items)

    @pytest.mark.asyncio
    async def test_region_mapping_crud(self, client: AsyncClient, db_session):
        ds_id = await self._create_ds(db_session)
        r = await client.post("/api/admin/mappings/region", json={
            "data_source_id": ds_id, "code": "310000", "level": "city", "name": "上海"
        })
        assert r.status_code == 200
        r = await client.get(f"/api/admin/mappings/region?data_source_id={ds_id}")
        assert r.status_code == 200


class TestAdminConfig:
    @pytest.mark.asyncio
    async def test_hotwords_returns_items(self, client: AsyncClient):
        r = await client.get("/api/admin/hotwords")
        assert r.status_code == 200
        assert len(r.json()["items"]) > 0

    @pytest.mark.asyncio
    async def test_fixed_periods_returns_items(self, client: AsyncClient):
        r = await client.get("/api/admin/fixed-periods")
        assert r.status_code == 200
        assert len(r.json()["items"]) >= 2

    @pytest.mark.asyncio
    async def test_audit_policy_roundtrip(self, client: AsyncClient):
        r = await client.put("/api/admin/audit-policy", json={"mode": "all"})
        assert r.status_code == 200
        r = await client.get("/api/admin/audit-policy")
        assert r.json()["mode"] == "all"
