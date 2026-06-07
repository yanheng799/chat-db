"""Tests for L0 learning logic and orchestrator."""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import select

from metadata.models import MetadataColumn, MetadataLearningLog, MetadataTable


class TestL0CommentExtraction:
    """Verify L0 copies column_comment / table_comment to semantic_description."""

    async def _create_data_source(self, session, ds_id):
        """Helper: create a DataSource row to satisfy FK constraints."""
        from config.data_source_model import DataSource
        from config.encryption import encrypt_value, generate_fernet_key

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
        return ds_id

    async def _create_table_with_columns(self, session, ds_id, table_comment=None, columns=None):
        """Helper: create a DataSource + metadata table with columns."""
        await self._create_data_source(session, ds_id)

        table_id = uuid.uuid4()
        table = MetadataTable(
            id=table_id,
            data_source_id=ds_id,
            schema_name="public",
            table_name="orders",
            table_comment=table_comment,
        )
        session.add(table)
        await session.flush()

        for col_spec in (columns or []):
            col = MetadataColumn(
                id=uuid.uuid4(),
                table_id=table_id,
                column_name=col_spec["name"],
                data_type=col_spec.get("type", "text"),
                is_nullable=col_spec.get("nullable", True),
                column_comment=col_spec.get("comment"),
                is_primary_key=col_spec.get("pk", False),
                ordinal_position=col_spec.get("pos", 0),
            )
            session.add(col)
        await session.commit()
        return table_id

    @pytest.mark.asyncio
    async def test_l0_copies_column_comment_to_description(self, db_session):
        """L0 should copy column_comment to semantic_description with correct metadata."""
        from learning.orchestrator import run_l0

        ds_id = uuid.uuid4()
        table_id = await self._create_table_with_columns(
            db_session,
            ds_id,
            columns=[
                {"name": "status", "comment": "订单状态", "type": "varchar", "pos": 1},
            ],
        )

        await run_l0(db_session, ds_id)

        result = await db_session.execute(
            select(MetadataColumn).where(MetadataColumn.table_id == table_id)
        )
        col = result.scalar_one()
        assert col.semantic_description == "订单状态"
        assert col.description_source == "schema_comment"
        assert col.description_confidence == 1.0

    @pytest.mark.asyncio
    async def test_l0_skips_column_without_comment(self, db_session):
        """L0 should NOT set semantic_description for columns without comment."""
        from learning.orchestrator import run_l0

        ds_id = uuid.uuid4()
        table_id = await self._create_table_with_columns(
            db_session,
            ds_id,
            columns=[
                {"name": "id", "comment": None, "type": "integer", "pos": 1},
            ],
        )

        await run_l0(db_session, ds_id)

        result = await db_session.execute(
            select(MetadataColumn).where(MetadataColumn.table_id == table_id)
        )
        col = result.scalar_one()
        assert col.semantic_description is None
        assert col.description_source is None
        assert col.description_confidence is None

    @pytest.mark.asyncio
    async def test_l0_copies_table_comment_to_description(self, db_session):
        """L0 should copy table_comment to table-level semantic_description."""
        from learning.orchestrator import run_l0

        ds_id = uuid.uuid4()
        await self._create_table_with_columns(
            db_session, ds_id, table_comment="订单表"
        )

        await run_l0(db_session, ds_id)

        result = await db_session.execute(
            select(MetadataTable).where(MetadataTable.data_source_id == ds_id)
        )
        table = result.scalar_one()
        assert table.semantic_description == "订单表"
        assert table.description_source == "schema_comment"
        assert table.description_confidence == 1.0

    @pytest.mark.asyncio
    async def test_l0_skips_table_without_comment(self, db_session):
        """L0 should NOT set semantic_description for tables without comment."""
        from learning.orchestrator import run_l0

        ds_id = uuid.uuid4()
        await self._create_table_with_columns(
            db_session, ds_id, table_comment=None
        )

        await run_l0(db_session, ds_id)

        result = await db_session.execute(
            select(MetadataTable).where(MetadataTable.data_source_id == ds_id)
        )
        table = result.scalar_one()
        assert table.semantic_description is None

    @pytest.mark.asyncio
    async def test_l0_returns_count(self, db_session):
        """L0 should return count of columns covered."""
        from learning.orchestrator import run_l0

        ds_id = uuid.uuid4()
        table_id = uuid.uuid4()
        await self._create_data_source(db_session, ds_id)

        table = MetadataTable(
            id=table_id,
            data_source_id=ds_id,
            schema_name="public",
            table_name="orders",
        )
        db_session.add(table)
        await db_session.flush()

        for spec in [
            {"name": "status", "comment": "状态", "pos": 1},
            {"name": "id", "comment": None, "pos": 2},
            {"name": "amount", "comment": "金额", "pos": 3},
        ]:
            db_session.add(MetadataColumn(
                id=uuid.uuid4(),
                table_id=table_id,
                column_name=spec["name"],
                data_type="text",
                is_nullable=True,
                column_comment=spec["comment"],
                ordinal_position=spec["pos"],
            ))
        await db_session.commit()

        count = await run_l0(db_session, ds_id)
        assert count == 2  # status and amount have comments

    @pytest.mark.asyncio
    async def test_l0_handles_empty_data_source(self, db_session):
        """L0 should handle a data source with no tables gracefully."""
        from learning.orchestrator import run_l0

        ds_id = uuid.uuid4()
        count = await run_l0(db_session, ds_id)
        assert count == 0
