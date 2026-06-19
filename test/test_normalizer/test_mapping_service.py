"""Tests for value mapping center CRUD + seed (issue #24)."""

import uuid
import pytest
from sqlalchemy import select

from normalizer.mapping_service import (
    auto_collect_enum_seeds,
    cleanup_mappings,
    list_enum_aliases,
    list_name_mappings,
    list_regions,
    upsert_enum_alias,
    upsert_name_mapping,
    upsert_region,
)
from metadata.models import MetadataColumn, MetadataTable


async def _create_data_source(session, ds_id):
    from config.data_source_model import DataSource
    from config.encryption import encrypt_value, generate_fernet_key
    key = generate_fernet_key()
    session.add(DataSource(id=ds_id, name=f"map-{ds_id.hex[:8]}", engine="postgresql",
        host="localhost", port=5432, username="test", password_encrypted=encrypt_value("test", key), database="testdb"))
    await session.commit()


class TestEnumAliases:
    @pytest.mark.asyncio
    async def test_upsert_and_list(self, db_session):
        ds_id = uuid.uuid4()
        await _create_data_source(db_session, ds_id)
        await upsert_enum_alias(db_session, ds_id, "orders", "status", "completed", display="已完成", aliases=["完结","结了"])
        rows = await list_enum_aliases(db_session, ds_id)
        assert len(rows) == 1
        assert rows[0]["display"] == "已完成"
        assert "完结" in rows[0]["aliases"]

    @pytest.mark.asyncio
    async def test_upsert_is_idempotent(self, db_session):
        ds_id = uuid.uuid4()
        await _create_data_source(db_session, ds_id)
        await upsert_enum_alias(db_session, ds_id, "t", "c", "v", display="first")
        await upsert_enum_alias(db_session, ds_id, "t", "c", "v", display="second")
        rows = await list_enum_aliases(db_session, ds_id)
        assert len(rows) == 1
        assert rows[0]["display"] == "second"


class TestRegionDict:
    @pytest.mark.asyncio
    async def test_upsert_and_list(self, db_session):
        ds_id = uuid.uuid4()
        await _create_data_source(db_session, ds_id)
        await upsert_region(db_session, ds_id, code="310000", parent_code=None, level="province", name="上海", aliases=["魔都"])
        rows = await list_regions(db_session, ds_id)
        assert len(rows) >= 1
        assert rows[0]["name"] == "上海"


class TestNameMappings:
    @pytest.mark.asyncio
    async def test_upsert_and_list(self, db_session):
        ds_id = uuid.uuid4()
        await _create_data_source(db_session, ds_id)
        await upsert_name_mapping(db_session, ds_id, short_name="华为", full_name="Huawei Technologies", target_table="customers", aliases=["HW"])
        rows = await list_name_mappings(db_session, ds_id)
        assert len(rows) == 1
        assert rows[0]["full_name"] == "Huawei Technologies"


class TestAutoCollect:
    @pytest.mark.asyncio
    async def test_collects_detected_enum_values(self, db_session):
        ds_id = uuid.uuid4()
        await _create_data_source(db_session, ds_id)
        t = MetadataTable(id=uuid.uuid4(), data_source_id=ds_id, schema_name="public", table_name="orders")
        db_session.add(t)
        await db_session.flush()
        db_session.add(MetadataColumn(id=uuid.uuid4(), table_id=t.id, column_name="status", data_type="varchar", is_nullable=False, ordinal_position=1, detected_enum_values=["active","pending","completed"]))
        await db_session.commit()
        n = await auto_collect_enum_seeds(db_session, ds_id)
        assert n == 3
        rows = await list_enum_aliases(db_session, ds_id)
        assert len(rows) == 3


class TestCleanupMappings:
    @pytest.mark.asyncio
    async def test_cleanup_removes_all(self, db_session):
        ds_id = uuid.uuid4()
        await _create_data_source(db_session, ds_id)
        await upsert_enum_alias(db_session, ds_id, "t", "c", "v")
        await upsert_region(db_session, ds_id, code="x", parent_code=None, level="city", name="x")
        await upsert_name_mapping(db_session, ds_id, short_name="s", full_name="f")
        await cleanup_mappings(db_session, ds_id)
        assert (await list_enum_aliases(db_session, ds_id)) == []
        assert (await list_regions(db_session, ds_id)) == []
        assert (await list_name_mappings(db_session, ds_id)) == []
