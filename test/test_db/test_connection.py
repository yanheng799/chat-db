import pytest
from sqlalchemy.ext.asyncio import AsyncEngine


class TestConnectionManager:
    async def test_create_engine_for_pg(self, connection_manager, sample_pg_config: dict) -> None:
        engine = connection_manager.create_engine(sample_pg_config)
        assert isinstance(engine, AsyncEngine)

    async def test_get_engine_caches_by_id(self, connection_manager, sample_pg_config: dict) -> None:
        e1 = connection_manager.get_or_create(sample_pg_config["id"], sample_pg_config)
        e2 = connection_manager.get_or_create(sample_pg_config["id"], sample_pg_config)
        assert e1 is e2

    async def test_dispose_removes_engine(self, connection_manager, sample_pg_config: dict) -> None:
        ds_id = sample_pg_config["id"]
        connection_manager.get_or_create(ds_id, sample_pg_config)
        await connection_manager.dispose(ds_id)
        assert connection_manager.engine_count() == 0

    async def test_dispose_all_clears_everything(
        self, connection_manager, sample_pg_config: dict
    ) -> None:
        ds_a = sample_pg_config
        ds_b = {**sample_pg_config, "id": "00000000-0000-0000-0000-000000000001"}
        connection_manager.get_or_create(ds_a["id"], ds_a)
        connection_manager.get_or_create(ds_b["id"], ds_b)
        assert connection_manager.engine_count() == 2
        await connection_manager.dispose_all()
        assert connection_manager.engine_count() == 0
