"""Tests for L1 splitting orchestration and pattern detection integration."""

import uuid
from typing import Any
from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy import select

from metadata.models import MetadataColumn, MetadataTable


class TestL1SplittingOrchestrator:
    """Verify L1 splitting respects skip logic and writes correct metadata."""

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

    async def _create_table_with_columns(self, session, ds_id, columns=None):
        """Helper: create a MetadataTable with specified columns."""
        await self._create_data_source(session, ds_id)

        table_id = uuid.uuid4()
        table = MetadataTable(
            id=table_id,
            data_source_id=ds_id,
            schema_name="public",
            table_name="test_table",
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
                # Pre-set L0 fields to test skip logic
                semantic_description=col_spec.get("semantic_description"),
                description_source=col_spec.get("description_source"),
                description_confidence=col_spec.get("description_confidence"),
            )
            session.add(col)
        await session.commit()
        return table_id

    @pytest.mark.asyncio
    async def test_l1_splits_unannotated_column(self, db_session):
        """Column without L0 annotation should get L1 splitting result."""
        from learning.orchestrator import run_l1_splitting

        ds_id = uuid.uuid4()
        table_id = await self._create_table_with_columns(
            db_session,
            ds_id,
            columns=[
                {"name": "order_status", "type": "varchar", "pos": 1},
            ],
        )

        count = await run_l1_splitting(db_session, ds_id)

        result = await db_session.execute(
            select(MetadataColumn).where(MetadataColumn.table_id == table_id)
        )
        col = result.scalar_one()
        assert col.semantic_description == "订单状态"
        assert col.description_source == "rule_inference"
        assert col.description_confidence == 0.7
        assert count == 1

    @pytest.mark.asyncio
    async def test_l1_skips_already_annotated_column(self, db_session):
        """Column already annotated by L0 should NOT be overwritten by L1."""
        from learning.orchestrator import run_l1_splitting

        ds_id = uuid.uuid4()
        table_id = await self._create_table_with_columns(
            db_session,
            ds_id,
            columns=[
                {
                    "name": "order_status",
                    "type": "varchar",
                    "pos": 1,
                    "semantic_description": "订单状态(注释)",
                    "description_source": "schema_comment",
                    "description_confidence": 1.0,
                },
            ],
        )

        count = await run_l1_splitting(db_session, ds_id)

        result = await db_session.execute(
            select(MetadataColumn).where(MetadataColumn.table_id == table_id)
        )
        col = result.scalar_one()
        assert col.semantic_description == "订单状态(注释)"
        assert col.description_source == "schema_comment"
        assert col.description_confidence == 1.0
        assert count == 0

    @pytest.mark.asyncio
    async def test_l1_does_not_set_description_on_failure(self, db_session):
        """Column whose name can't be split should remain untouched."""
        from learning.orchestrator import run_l1_splitting

        ds_id = uuid.uuid4()
        table_id = await self._create_table_with_columns(
            db_session,
            ds_id,
            columns=[
                {"name": "xyz_unknown", "type": "text", "pos": 1},
            ],
        )

        count = await run_l1_splitting(db_session, ds_id)

        result = await db_session.execute(
            select(MetadataColumn).where(MetadataColumn.table_id == table_id)
        )
        col = result.scalar_one()
        assert col.semantic_description is None
        assert col.description_source is None
        assert col.description_confidence is None
        assert count == 0

    @pytest.mark.asyncio
    async def test_l1_mixed_columns(self, db_session):
        """Mix of annotated, splittable, and unsplittable columns."""
        from learning.orchestrator import run_l1_splitting

        ds_id = uuid.uuid4()
        table_id = await self._create_table_with_columns(
            db_session,
            ds_id,
            columns=[
                {
                    "name": "status",
                    "type": "varchar",
                    "pos": 1,
                    "semantic_description": "状态(注释)",
                    "description_source": "schema_comment",
                    "description_confidence": 1.0,
                },
                {"name": "total_amount", "type": "decimal", "pos": 2},
                {"name": "xyz_col", "type": "text", "pos": 3},
            ],
        )

        count = await run_l1_splitting(db_session, ds_id)

        result = await db_session.execute(
            select(MetadataColumn).where(MetadataColumn.table_id == table_id)
            .order_by(MetadataColumn.ordinal_position)
        )
        cols = result.scalars().all()
        assert len(cols) == 3
        # L0-annotated: unchanged
        assert cols[0].semantic_description == "状态(注释)"
        assert cols[0].description_source == "schema_comment"
        # L1-splittable: filled
        assert cols[1].semantic_description == "总金额"
        assert cols[1].description_source == "rule_inference"
        assert cols[1].description_confidence == 0.7
        # Unsplittable: untouched
        assert cols[2].semantic_description is None
        assert count == 1  # only total_amount was newly described

    @pytest.mark.asyncio
    async def test_l1_handles_empty_data_source(self, db_session):
        """L1 splitting should handle a data source with no tables gracefully."""
        from learning.orchestrator import run_l1_splitting

        ds_id = uuid.uuid4()
        count = await run_l1_splitting(db_session, ds_id)
        assert count == 0


class TestL1PatternDetection:
    """Verify L1 pattern detection writes correct fields via mock query executor."""

    async def _create_data_source(self, session, ds_id, engine="postgresql"):
        from config.data_source_model import DataSource
        from config.encryption import encrypt_value, generate_fernet_key

        key = generate_fernet_key()
        ds = DataSource(
            id=ds_id,
            name=f"test-ds-{ds_id.hex[:8]}",
            engine=engine,
            host="localhost",
            port=5432,
            username="test",
            password_encrypted=encrypt_value("test", key),
            database="testdb",
        )
        session.add(ds)
        await session.flush()

    async def _create_table_with_columns(self, session, ds_id, table_name="orders", columns=None, schema_name="public"):
        await self._create_data_source(session, ds_id)
        table_id = uuid.uuid4()
        table = MetadataTable(
            id=table_id,
            data_source_id=ds_id,
            schema_name=schema_name,
            table_name=table_name,
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
                semantic_description=col_spec.get("semantic_description"),
                description_source=col_spec.get("description_source"),
                description_confidence=col_spec.get("description_confidence"),
            )
            session.add(col)
        await session.commit()
        return table_id

    def _make_mock_executor(self, rows: dict[str, dict[str, Any]]):
        """Create a mock query executor returning pre-configured results per table.

        *rows* maps ``table_name`` → aggregate result dict.
        Also handles the estimated-rows query by returning a default.
        """
        async def _executor(sql: str) -> dict[str, Any]:
            if "pg_class" in sql or "EXPLAIN" in sql:
                return {"estimate": 500}
            for table_name, row in rows.items():
                if table_name in sql:
                    return row
            return {"total_rows": 0}

        return _executor

    @pytest.mark.asyncio
    async def test_pattern_detection_writes_enum_values(self, db_session):
        """Enum column should get detected_enum_values populated."""
        from learning.orchestrator import run_l1_pattern_detection

        ds_id = uuid.uuid4()
        table_id = await self._create_table_with_columns(
            db_session, ds_id, table_name="orders",
            columns=[
                {"name": "status", "type": "varchar", "pos": 1},
                {"name": "amount", "type": "numeric", "pos": 2},
            ],
        )

        mock_executor = self._make_mock_executor({
            "orders": {
                "total_rows": 1000,
                "status__distinct": 3,
                "status__null_count": 5,
                "status__values": ["active", "pending", "closed"],
                "amount__distinct": 800,
                "amount__null_count": 0,
                "amount__min": 10.0,
                "amount__max": 999.99,
                "amount__values": None,
            },
        })

        count = await run_l1_pattern_detection(
            db_session, ds_id, query_executor=mock_executor, engine_type="postgresql"
        )

        result = await db_session.execute(
            select(MetadataColumn).where(MetadataColumn.table_id == table_id)
            .order_by(MetadataColumn.ordinal_position)
        )
        cols = result.scalars().all()

        # status: enum detected (3/1000 = 0.003 < 0.05 AND 3 ≤ 20)
        assert cols[0].detected_enum_values == ["active", "pending", "closed"]
        assert cols[0].null_ratio == pytest.approx(0.005)
        # amount: not enum, has numeric range
        assert cols[1].detected_enum_values is None
        assert cols[1].null_ratio == pytest.approx(0.0)
        assert cols[1].numeric_range == {"min": 10.0, "max": 999.99}
        assert count == 2  # both columns processed

    @pytest.mark.asyncio
    async def test_pattern_detection_runs_on_annotated_columns(self, db_session):
        """Pattern detection should run on ALL columns, even L0-annotated ones."""
        from learning.orchestrator import run_l1_pattern_detection

        ds_id = uuid.uuid4()
        table_id = await self._create_table_with_columns(
            db_session, ds_id, table_name="orders",
            columns=[
                {
                    "name": "status", "type": "varchar", "pos": 1,
                    "semantic_description": "状态(注释)",
                    "description_source": "schema_comment",
                    "description_confidence": 1.0,
                },
            ],
        )

        mock_executor = self._make_mock_executor({
            "orders": {
                "total_rows": 100,
                "status__distinct": 4,
                "status__null_count": 0,
                "status__values": ["active", "pending", "closed", "cancelled"],
            },
        })

        await run_l1_pattern_detection(
            db_session, ds_id, query_executor=mock_executor, engine_type="postgresql"
        )

        result = await db_session.execute(
            select(MetadataColumn).where(MetadataColumn.table_id == table_id)
        )
        col = result.scalar_one()
        # Pattern detection wrote data, but L0 description stays
        assert col.semantic_description == "状态(注释)"
        assert col.detected_enum_values == ["active", "pending", "closed", "cancelled"]

    @pytest.mark.asyncio
    async def test_pattern_detection_handles_empty_data_source(self, db_session):
        """Pattern detection should handle no tables gracefully."""
        from learning.orchestrator import run_l1_pattern_detection

        ds_id = uuid.uuid4()

        async def _no_tables_executor(sql):
            return {"estimate": 0}

        count = await run_l1_pattern_detection(
            db_session, ds_id, query_executor=_no_tables_executor, engine_type="postgresql"
        )
        assert count == 0

    @pytest.mark.asyncio
    async def test_pattern_detection_no_enum_for_high_cardinality(self, db_session):
        """High-cardinality column should not get detected_enum_values."""
        from learning.orchestrator import run_l1_pattern_detection

        ds_id = uuid.uuid4()
        table_id = await self._create_table_with_columns(
            db_session, ds_id, table_name="users",
            columns=[
                {"name": "email", "type": "varchar", "pos": 1},
            ],
        )

        mock_executor = self._make_mock_executor({
            "users": {
                "total_rows": 100,
                "email__distinct": 95,  # 95/100 = 0.95 → not enum
                "email__null_count": 2,
                "email__values": None,
            },
        })

        await run_l1_pattern_detection(
            db_session, ds_id, query_executor=mock_executor, engine_type="postgresql"
        )

        result = await db_session.execute(
            select(MetadataColumn).where(MetadataColumn.table_id == table_id)
        )
        col = result.scalar_one()
        assert col.detected_enum_values is None  # too many distinct values
        assert col.null_ratio == pytest.approx(0.02)

    @pytest.mark.asyncio
    async def test_pattern_detection_numeric_range_only_for_numeric(self, db_session):
        """numeric_range should only be set for numeric type columns."""
        from learning.orchestrator import run_l1_pattern_detection

        ds_id = uuid.uuid4()
        table_id = await self._create_table_with_columns(
            db_session, ds_id, table_name="orders",
            columns=[
                {"name": "status", "type": "varchar", "pos": 1},
                {"name": "amount", "type": "integer", "pos": 2},
            ],
        )

        mock_executor = self._make_mock_executor({
            "orders": {
                "total_rows": 100,
                "status__distinct": 3,
                "status__null_count": 0,
                "status__values": ["a", "b", "c"],
                "amount__distinct": 50,
                "amount__null_count": 10,
                "amount__min": 1,
                "amount__max": 1000,
                "amount__values": None,
            },
        })

        await run_l1_pattern_detection(
            db_session, ds_id, query_executor=mock_executor, engine_type="postgresql"
        )

        result = await db_session.execute(
            select(MetadataColumn).where(MetadataColumn.table_id == table_id)
            .order_by(MetadataColumn.ordinal_position)
        )
        cols = result.scalars().all()
        # varchar: no numeric_range
        assert cols[0].numeric_range is None
        # integer: has numeric_range
        assert cols[1].numeric_range == {"min": 1, "max": 1000}
