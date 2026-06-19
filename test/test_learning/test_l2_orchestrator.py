"""Tests for L2 orchestrator integration — mock LLM, structured signals, independent sessions."""

import uuid
from typing import Any

import pytest
from sqlalchemy import select

from metadata.models import MetadataColumn, MetadataTable


class TestL2Orchestrator:
    """Verify L2 inference writes descriptions via mock LLM using independent sessions."""

    async def _create_data_source(self, session, ds_id):
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

    async def _create_table_with_columns(self, session, ds_id, table_name="orders", columns=None):
        from config.data_source_model import DataSource
        from sqlalchemy import select as _sel

        existing = await session.execute(_sel(DataSource).where(DataSource.id == ds_id))
        if existing.scalar_one_or_none() is None:
            await self._create_data_source(session, ds_id)
        table_id = uuid.uuid4()
        table = MetadataTable(
            id=table_id,
            data_source_id=ds_id,
            schema_name="public",
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
                detected_enum_values=col_spec.get("enum_values"),
            )
            session.add(col)
        await session.commit()
        return table_id

    def _make_mock_llm(self, responses: dict[str, str]):
        """Return a mock LLM caller that maps table names to responses."""

        async def _caller(system_prompt: str, user_prompt: str) -> str:
            for table_name, response in responses.items():
                if table_name in user_prompt:
                    return response
            return '{"columns": {}}'

        return _caller

    @pytest.mark.asyncio
    async def test_l2_writes_descriptions_for_uncovered_fields(self, db_session, session_factory):
        """L2 should write semantic_description for fields not covered by L0/L1."""
        from learning.orchestrator import run_l2_inference

        ds_id = uuid.uuid4()
        table_id = await self._create_table_with_columns(
            db_session, ds_id, table_name="products",
            columns=[
                {"name": "sku_code", "type": "varchar", "pos": 1},  # uncovered
                {"name": "shelf_pos", "type": "integer", "pos": 2},  # uncovered
                {
                    "name": "status", "type": "varchar", "pos": 3,
                    "semantic_description": "状态",
                    "description_source": "schema_comment",
                    "description_confidence": 1.0,
                },
            ],
        )

        mock_llm = self._make_mock_llm({
            "products": '{"columns": {"sku_code": "SKU编码", "shelf_pos": "货架位置"}}',
        })

        l2_count, llm_calls = await run_l2_inference(
            session_factory, ds_id,
            llm_caller=mock_llm,
        )

        result = await db_session.execute(
            select(MetadataColumn).where(MetadataColumn.table_id == table_id)
            .order_by(MetadataColumn.ordinal_position)
        )
        cols = result.scalars().all()

        assert cols[0].semantic_description == "SKU编码"
        assert cols[0].description_source == "llm_inference"
        assert cols[0].description_confidence == 0.5
        assert cols[1].semantic_description == "货架位置"
        assert cols[1].description_source == "llm_inference"
        # L0-annotated: unchanged
        assert cols[2].semantic_description == "状态"
        assert cols[2].description_source == "schema_comment"
        assert l2_count == 2
        assert llm_calls == 1

    @pytest.mark.asyncio
    async def test_l2_skips_fully_covered_table(self, db_session, session_factory):
        """L2 should skip tables where all columns are already described."""
        from learning.orchestrator import run_l2_inference

        ds_id = uuid.uuid4()
        await self._create_table_with_columns(
            db_session, ds_id, table_name="orders",
            columns=[
                {
                    "name": "status", "type": "varchar", "pos": 1,
                    "semantic_description": "订单状态",
                    "description_source": "rule_inference",
                },
            ],
        )

        mock_llm = self._make_mock_llm({})

        l2_count, llm_calls = await run_l2_inference(
            session_factory, ds_id,
            llm_caller=mock_llm,
        )
        assert l2_count == 0
        assert llm_calls == 0

    @pytest.mark.asyncio
    async def test_l2_handles_llm_failure_gracefully(self, db_session, session_factory):
        """L2 should handle LLM failure without crashing."""
        from learning.orchestrator import run_l2_inference

        ds_id = uuid.uuid4()
        table_id = await self._create_table_with_columns(
            db_session, ds_id, table_name="orders",
            columns=[
                {"name": "xyz_col", "type": "text", "pos": 1},
            ],
        )

        async def failing_llm(system_prompt, user_prompt):
            raise ConnectionError("LLM unavailable")

        l2_count, llm_calls = await run_l2_inference(
            session_factory, ds_id,
            llm_caller=failing_llm,
        )

        result = await db_session.execute(
            select(MetadataColumn).where(MetadataColumn.table_id == table_id)
        )
        col = result.scalar_one()
        assert col.semantic_description is None
        assert l2_count == 0
        assert llm_calls == 1  # still counted as an LLM call attempt

    @pytest.mark.asyncio
    async def test_l2_handles_empty_data_source(self, db_session, session_factory):
        """L2 should handle a data source with no tables."""
        from learning.orchestrator import run_l2_inference

        ds_id = uuid.uuid4()
        l2_count, llm_calls = await run_l2_inference(
            session_factory, ds_id,
            llm_caller=self._make_mock_llm({}),
        )
        assert l2_count == 0
        assert llm_calls == 0

    @pytest.mark.asyncio
    async def test_l2_concurrent_tables_use_independent_sessions(self, db_session, session_factory):
        """>max_concurrency tables each get an independent AsyncSession.

        With a single shared session SQLAlchemy would raise a concurrent-use
        error, which ``gather(return_exceptions=True)`` would swallow — yielding
        fewer described columns than tables. Asserting all tables are described
        proves each task used its own session without concurrency errors.
        """
        from learning.orchestrator import run_l2_inference

        ds_id = uuid.uuid4()
        # 6 tables > default max_concurrency=5 → forces semaphore queuing and
        # concurrent session usage.
        for i in range(6):
            await self._create_table_with_columns(
                db_session, ds_id, table_name=f"table_{i}",
                columns=[{"name": f"col_{i}", "type": "text", "pos": 1}],
            )

        mock_llm = self._make_mock_llm({
            f"table_{i}": f'{{"columns": {{"col_{i}": "字段{i}"}}}}' for i in range(6)
        })

        l2_count, llm_calls = await run_l2_inference(
            session_factory, ds_id,
            llm_caller=mock_llm,
            max_concurrency=5,
        )
        assert llm_calls == 6
        assert l2_count == 6

    @pytest.mark.asyncio
    async def test_l2_stops_early_at_max_calls(self, db_session, session_factory):
        """L2 must stop issuing LLM calls once max_calls is reached."""
        from learning.orchestrator import run_l2_inference

        ds_id = uuid.uuid4()
        for i in range(3):
            await self._create_table_with_columns(
                db_session, ds_id, table_name=f"cap_{i}",
                columns=[{"name": f"col_{i}", "type": "text", "pos": 1}],
            )
        mock_llm = self._make_mock_llm({
            f"cap_{i}": f'{{"columns": {{"col_{i}": "x"}}}}' for i in range(3)
        })

        l2_count, llm_calls = await run_l2_inference(
            session_factory, ds_id,
            llm_caller=mock_llm,
            max_calls=1,
        )
        # Only one table gets an LLM call; the rest are skipped.
        assert llm_calls == 1
        assert l2_count == 1

    @pytest.mark.asyncio
    async def test_l2_max_calls_zero_means_unlimited(self, db_session, session_factory):
        """max_calls=0 disables the cap; all eligible tables are processed."""
        from learning.orchestrator import run_l2_inference

        ds_id = uuid.uuid4()
        for i in range(3):
            await self._create_table_with_columns(
                db_session, ds_id, table_name=f"un_{i}",
                columns=[{"name": f"c_{i}", "type": "text", "pos": 1}],
            )
        mock_llm = self._make_mock_llm({
            f"un_{i}": f'{{"columns": {{"c_{i}": "x"}}}}' for i in range(3)
        })

        l2_count, llm_calls = await run_l2_inference(
            session_factory, ds_id,
            llm_caller=mock_llm,
            max_calls=0,
        )
        assert llm_calls == 3
        assert l2_count == 3

    @pytest.mark.asyncio
    async def test_l2_prompt_carries_no_raw_business_data(self, db_session, session_factory):
        """The LLM prompt must contain structured signals only, no raw rows."""
        from learning.orchestrator import run_l2_inference

        ds_id = uuid.uuid4()
        await self._create_table_with_columns(
            db_session, ds_id, table_name="secrets",
            columns=[{"name": "ssn_col", "type": "varchar", "pos": 1}],
        )

        captured: dict[str, Any] = {}

        async def capturing_llm(system_prompt: str, user_prompt: str) -> str:
            captured["prompt"] = user_prompt
            return '{"columns": {"ssn_col": "社保号"}}'

        await run_l2_inference(
            session_factory, ds_id,
            llm_caller=capturing_llm,
        )
        assert "业务数据" in captured["prompt"]
        assert "样本数据" not in captured["prompt"]
