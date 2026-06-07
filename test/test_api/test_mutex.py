"""Tests for L0 staleness refresh and learning/sync mutual exclusion."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from api.main import app
from config.database import get_session
from config.encryption import encrypt_value, generate_fernet_key
from metadata.models import MetadataColumn, MetadataLearningLog, MetadataSyncLog, MetadataTable


@pytest.fixture()
async def client_with_db():
    """Client with real DB session, cleans tables before/after."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from config.settings import Settings

    settings = Settings()
    engine = create_async_engine(
        f"postgresql+asyncpg://{settings.postgres_user}"
        f":{settings.postgres_password}"
        f"@{settings.postgres_host}"
        f":{settings.postgres_port}"
        f"/{settings.postgres_db}",
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        from metadata.models import MetadataChangeLog, MetadataForeignKey, MetadataIndex

        await session.execute(MetadataChangeLog.__table__.delete())
        await session.execute(MetadataForeignKey.__table__.delete())
        await session.execute(MetadataIndex.__table__.delete())
        await session.execute(MetadataColumn.__table__.delete())
        await session.execute(MetadataTable.__table__.delete())
        await session.execute(MetadataSyncLog.__table__.delete())
        await session.execute(MetadataLearningLog.__table__.delete())
        from config.data_source_model import DataSource

        await session.execute(DataSource.__table__.delete())
        await session.commit()

    async def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, session
    app.dependency_overrides.clear()
    await engine.dispose()


class TestL0StalenessRefresh:
    """Verify L0 descriptions are refreshed after comment changes in sync."""

    async def _create_ds_and_metadata(
        self, session, ds_id, table_comment=None, columns=None
    ):
        from config.data_source_model import DataSource

        key = generate_fernet_key()
        ds = DataSource(
            id=ds_id,
            name=f"test-ds-{ds_id.hex[:8]}",
            engine="postgresql",
            host="localhost",
            port=5432,
            username="test",
            password_encrypted=encrypt_value("test", key),
            database="testdb",
        )
        session.add(ds)
        await session.flush()

        table_id = uuid.uuid4()
        table = MetadataTable(
            id=table_id,
            data_source_id=ds_id,
            schema_name="public",
            table_name="orders",
            table_comment=table_comment,
            semantic_description=table_comment,
            description_source="schema_comment" if table_comment else None,
            description_confidence=1.0 if table_comment else None,
        )
        session.add(table)
        await session.flush()

        for i, col_spec in enumerate(columns or []):
            col = MetadataColumn(
                id=uuid.uuid4(),
                table_id=table_id,
                column_name=col_spec["name"],
                data_type=col_spec.get("type", "text"),
                is_nullable=col_spec.get("nullable", True),
                column_comment=col_spec.get("comment"),
                is_primary_key=col_spec.get("pk", False),
                ordinal_position=col_spec.get("pos", i + 1),
                semantic_description=col_spec.get("comment"),
                description_source="schema_comment" if col_spec.get("comment") else None,
                description_confidence=1.0 if col_spec.get("comment") else None,
            )
            session.add(col)
        await session.commit()
        return table_id

    @pytest.mark.asyncio
    async def test_refresh_updates_column_description(self, db_session):
        """When column_comment changes, L0 staleness refresh updates semantic_description."""
        from api.datasources import _refresh_l0_descriptions

        ds_id = uuid.uuid4()
        table_id = await self._create_ds_and_metadata(
            db_session,
            ds_id,
            columns=[
                {"name": "status", "type": "varchar", "comment": "订单状态"},
                {"name": "amount", "type": "numeric", "comment": "金额"},
            ],
        )

        # Simulate a sync that detected column_comment change for "status"
        changes = [
            {
                "change_type": "column_modified",
                "schema_name": "public",
                "table_name": "orders",
                "object_name": "status",
                "before_value": {
                    "table_schema": "public",
                    "table_name": "orders",
                    "column_name": "status",
                    "data_type": "varchar",
                    "is_nullable": "YES",
                    "column_comment": "订单状态",
                },
                "after_value": {
                    "table_schema": "public",
                    "table_name": "orders",
                    "column_name": "status",
                    "data_type": "varchar",
                    "is_nullable": "YES",
                    "column_comment": "订单状态（新建/处理中/已完成）",
                },
            },
        ]

        # First update the column_comment in the metadata to simulate what _apply_changes did
        result = await db_session.execute(
            select(MetadataColumn).where(
                MetadataColumn.table_id == table_id,
                MetadataColumn.column_name == "status",
            )
        )
        col = result.scalar_one()
        col.column_comment = "订单状态（新建/处理中/已完成）"
        await db_session.commit()

        await _refresh_l0_descriptions(db_session, changes, ds_id)

        result = await db_session.execute(
            select(MetadataColumn).where(
                MetadataColumn.table_id == table_id,
                MetadataColumn.column_name == "status",
            )
        )
        col = result.scalar_one()
        assert col.semantic_description == "订单状态（新建/处理中/已完成）"
        assert col.description_source == "schema_comment"

        # Other column unchanged
        result = await db_session.execute(
            select(MetadataColumn).where(
                MetadataColumn.table_id == table_id,
                MetadataColumn.column_name == "amount",
            )
        )
        other = result.scalar_one()
        assert other.semantic_description == "金额"

    @pytest.mark.asyncio
    async def test_refresh_does_not_affect_non_schema_comment_fields(self, db_session):
        """Fields with description_source != schema_comment should NOT be updated."""
        from api.datasources import _refresh_l0_descriptions

        ds_id = uuid.uuid4()
        table_id = await self._create_ds_and_metadata(
            db_session,
            ds_id,
            columns=[
                {"name": "total_amount", "type": "numeric", "comment": None},
            ],
        )

        # Set L1 description
        result = await db_session.execute(
            select(MetadataColumn).where(
                MetadataColumn.table_id == table_id,
                MetadataColumn.column_name == "total_amount",
            )
        )
        col = result.scalar_one()
        col.semantic_description = "总金额"
        col.description_source = "rule_inference"
        col.description_confidence = 0.7
        await db_session.commit()

        changes = []  # No changes — but even if there were, non-schema_comment should be safe
        await _refresh_l0_descriptions(db_session, changes, ds_id)

        result = await db_session.execute(
            select(MetadataColumn).where(MetadataColumn.table_id == table_id)
        )
        col = result.scalar_one()
        assert col.description_source == "rule_inference"
        assert col.semantic_description == "总金额"

    @pytest.mark.asyncio
    async def test_refresh_updates_table_description(self, db_session):
        """When table_comment changes, L0 staleness refresh updates table-level semantic_description."""
        from api.datasources import _refresh_l0_descriptions

        ds_id = uuid.uuid4()
        table_id = await self._create_ds_and_metadata(
            db_session, ds_id, table_comment="订单"
        )

        # Simulate table_comment change
        result = await db_session.execute(
            select(MetadataTable).where(MetadataTable.id == table_id)
        )
        table = result.scalar_one()
        table.table_comment = "订单主表"
        await db_session.commit()

        changes = [
            {
                "change_type": "table_modified",
                "schema_name": "public",
                "table_name": "orders",
                "object_name": "orders",
                "before_value": {
                    "table_schema": "public",
                    "table_name": "orders",
                    "table_comment": "订单",
                },
                "after_value": {
                    "table_schema": "public",
                    "table_name": "orders",
                    "table_comment": "订单主表",
                },
            },
        ]

        await _refresh_l0_descriptions(db_session, changes, ds_id)

        result = await db_session.execute(
            select(MetadataTable).where(MetadataTable.id == table_id)
        )
        table = result.scalar_one()
        assert table.semantic_description == "订单主表"
        assert table.description_source == "schema_comment"


class TestLearningSyncMutex:
    """Verify learning/sync mutual exclusion — 409 Conflict."""

    async def _create_ds(self, client, fernet_key):
        import os

        os.environ["ENCRYPTION_KEY"] = fernet_key
        r = await client.post(
            "/api/datasources",
            json={
                "name": f"mutex-test-{uuid.uuid4().hex[:8]}",
                "engine": "postgresql",
                "host": "127.0.0.1",
                "port": 5432,
                "username": "u",
                "password": "p",
                "database": "d",
            },
        )
        assert r.status_code == 201
        return r.json()["id"]

    @pytest.mark.asyncio
    async def test_learn_returns_409_when_sync_running(self, client_with_db):
        """POST /learn should return 409 if a sync is running."""
        client, session = client_with_db
        fernet_key = generate_fernet_key()

        ds_id = await self._create_ds(client, fernet_key)

        # Create a running sync log
        sync_log = MetadataSyncLog(
            id=uuid.uuid4(),
            data_source_id=uuid.UUID(ds_id),
            sync_type="manual",
            status="running",
        )
        session.add(sync_log)
        await session.commit()

        r = await client.post(f"/api/datasources/{ds_id}/learn")
        assert r.status_code == 409
        assert "sync" in r.json()["detail"].lower() or "conflict" in r.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_sync_returns_409_when_learning_running(self, client_with_db):
        """POST /sync should return 409 if a learning task is running."""
        client, session = client_with_db
        fernet_key = generate_fernet_key()

        ds_id = await self._create_ds(client, fernet_key)

        # Create a running learning log
        learning_log = MetadataLearningLog(
            id=uuid.uuid4(),
            data_source_id=uuid.UUID(ds_id),
            trigger_type="manual",
            status="running",
        )
        session.add(learning_log)
        await session.commit()

        r = await client.post(f"/api/datasources/{ds_id}/sync")
        assert r.status_code == 409
        assert "learn" in r.json()["detail"].lower() or "conflict" in r.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_learn_succeeds_when_no_sync_running(self, client_with_db):
        """POST /learn should succeed when no sync is running."""
        client, session = client_with_db
        fernet_key = generate_fernet_key()

        ds_id = await self._create_ds(client, fernet_key)

        r = await client.post(f"/api/datasources/{ds_id}/learn")
        assert r.status_code == 202
