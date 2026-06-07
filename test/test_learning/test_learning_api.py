"""Tests for learning API endpoints."""

import uuid

import pytest
from httpx import AsyncClient

from config.data_source_model import DataSource
from config.encryption import encrypt_value, generate_fernet_key
from metadata.models import MetadataColumn, MetadataLearningLog, MetadataTable


async def _create_ds_with_metadata(client: AsyncClient, db_session) -> uuid.UUID:
    """Helper: create a data source via API and insert metadata directly."""
    key = generate_fernet_key()
    ds_id = uuid.uuid4()
    ds = DataSource(
        id=ds_id,
        name=f"learn-test-{ds_id.hex[:8]}",
        engine="postgresql",
        host="localhost",
        port=5432,
        username="test",
        password_encrypted=encrypt_value("test", key),
        database="testdb",
    )
    db_session.add(ds)
    await db_session.commit()
    return ds_id


class TestLearnEndpoint:
    """POST /api/datasources/{id}/learn"""

    @pytest.mark.asyncio
    async def test_learn_returns_202_and_starts_learning(self, client, db_session):
        ds_id = await _create_ds_with_metadata(client, db_session)
        resp = await client.post(f"/api/datasources/{ds_id}/learn")
        assert resp.status_code == 202
        data = resp.json()
        assert "learning_log_id" in data
        assert "message" in data

    @pytest.mark.asyncio
    async def test_learn_creates_running_log(self, client, db_session):
        ds_id = await _create_ds_with_metadata(client, db_session)
        resp = await client.post(f"/api/datasources/{ds_id}/learn")
        log_id = uuid.UUID(resp.json()["learning_log_id"])

        # Since L0 runs synchronously in this issue, log should be completed
        from sqlalchemy import select

        result = await db_session.execute(
            select(MetadataLearningLog).where(MetadataLearningLog.id == log_id)
        )
        log = result.scalar_one()
        assert log.trigger_type == "manual"
        assert log.status in ("success", "partial_success", "failed")

    @pytest.mark.asyncio
    async def test_learn_returns_404_for_nonexistent_ds(self, client, db_session):
        fake_id = uuid.uuid4()
        resp = await client.post(f"/api/datasources/{fake_id}/learn")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_learn_fills_l0_for_commented_columns(self, client, db_session):
        ds_id = await _create_ds_with_metadata(client, db_session)

        # Insert metadata with comments
        table_id = uuid.uuid4()
        db_session.add(MetadataTable(
            id=table_id,
            data_source_id=ds_id,
            schema_name="public",
            table_name="orders",
            table_comment="订单表",
        ))
        await db_session.flush()
        db_session.add(MetadataColumn(
            id=uuid.uuid4(),
            table_id=table_id,
            column_name="status",
            data_type="varchar",
            is_nullable=False,
            column_comment="订单状态",
            ordinal_position=1,
        ))
        await db_session.commit()

        resp = await client.post(f"/api/datasources/{ds_id}/learn")
        assert resp.status_code == 202

        # Verify L0 filled semantic_description
        from sqlalchemy import select

        result = await db_session.execute(
            select(MetadataColumn).where(MetadataColumn.table_id == table_id)
        )
        col = result.scalar_one()
        assert col.semantic_description == "订单状态"
        assert col.description_source == "schema_comment"

        # Verify table-level too
        result = await db_session.execute(
            select(MetadataTable).where(MetadataTable.id == table_id)
        )
        table = result.scalar_one()
        assert table.semantic_description == "订单表"


class TestLearningLogsEndpoint:
    """GET /api/datasources/{id}/learning-logs"""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_logs(self, client, db_session):
        ds_id = await _create_ds_with_metadata(client, db_session)
        resp = await client.get(f"/api/datasources/{ds_id}/learning-logs")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_returns_logs_after_learning(self, client, db_session):
        ds_id = await _create_ds_with_metadata(client, db_session)
        await client.post(f"/api/datasources/{ds_id}/learn")

        resp = await client.get(f"/api/datasources/{ds_id}/learning-logs")
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) >= 1
        log = logs[0]
        assert log["data_source_id"] == str(ds_id)
        assert log["trigger_type"] == "manual"
        assert log["status"] in ("success", "partial_success", "failed")
        assert "started_at" in log

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_ds(self, client, db_session):
        fake_id = uuid.uuid4()
        resp = await client.get(f"/api/datasources/{fake_id}/learning-logs")
        assert resp.status_code == 404
