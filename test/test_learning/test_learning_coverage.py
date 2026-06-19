"""Tests for run_learning coverage metric and status determination (Issue 002).

Coverage must equal the number of columns with a non-null ``semantic_description``
divided by total columns — not the summed l0+l1+l2 counts, which historically
double-counted L1 pattern detection (it writes ``null_ratio`` to ~every column
without writing ``semantic_description``) and could push the ratio past 100%.
"""

import uuid

import pytest
from sqlalchemy import select

from metadata.models import MetadataColumn, MetadataLearningLog, MetadataTable


async def _create_data_source(session, ds_id):
    from config.data_source_model import DataSource
    from config.encryption import encrypt_value, generate_fernet_key

    key = generate_fernet_key()
    session.add(
        DataSource(
            id=ds_id,
            name=f"cov-{ds_id.hex[:8]}",
            engine="postgresql",
            host="localhost",
            port=5432,
            username="test",
            password_encrypted=encrypt_value("test", key),
            database="testdb",
        )
    )
    await session.commit()


async def _create_table_with_columns(session, ds_id, columns, table_name="orders"):
    table_id = uuid.uuid4()
    session.add(
        MetadataTable(
            id=table_id,
            data_source_id=ds_id,
            schema_name="public",
            table_name=table_name,
        )
    )
    await session.flush()
    for i, spec in enumerate(columns):
        session.add(
            MetadataColumn(
                id=uuid.uuid4(),
                table_id=table_id,
                column_name=spec["name"],
                data_type=spec.get("type", "text"),
                is_nullable=True,
                column_comment=spec.get("comment"),
                is_primary_key=spec.get("pk", False),
                ordinal_position=i + 1,
                null_ratio=spec.get("null_ratio"),
            )
        )
    await session.commit()
    return table_id


async def _fetch_log(session, log_id):
    result = await session.execute(
        select(MetadataLearningLog).where(MetadataLearningLog.id == log_id)
    )
    return result.scalar_one()


class TestLearningCoverage:
    """Verify coverage metric counts semantic_description non-null columns only."""

    @pytest.mark.asyncio
    async def test_coverage_not_inflated_by_pattern_detection(self, db_session, monkeypatch):
        """Pattern detection reporting many 'updated' columns must NOT inflate coverage.

        Simulates the original bug: L1 pattern detection writes structural stats
        (null_ratio) to columns and reports a high count, but those columns have
        no semantic_description. Coverage must stay 0 → failed.
        """
        from learning import orchestrator
        from learning.orchestrator import run_learning

        async def fake_pattern_detection(session, data_source_id):
            # Pretend pattern detection "described" 100 columns.
            return 100

        monkeypatch.setattr(
            orchestrator, "_run_pattern_detection_with_ds", fake_pattern_detection
        )

        ds_id = uuid.uuid4()
        await _create_data_source(db_session, ds_id)
        # 3 columns, none described (no comments, unsplittable names).
        await _create_table_with_columns(
            db_session,
            ds_id,
            columns=[
                {"name": "usr_typ_cd", "null_ratio": 0.1},
                {"name": "qwxz_foo", "null_ratio": 0.2},
                {"name": "abc_zz", "null_ratio": 0.0},
            ],
        )

        log_id = await run_learning(db_session, ds_id)
        log = await _fetch_log(db_session, log_id)

        # No column has a semantic_description → coverage 0 → failed,
        # regardless of the 100 pattern-detection "updates".
        assert log.columns_described == 0
        assert log.status == "failed"

    @pytest.mark.asyncio
    async def test_empty_data_source_is_failed(self, db_session):
        """An empty data source (no columns) must be `failed`, not `success`."""
        from learning.orchestrator import run_learning

        ds_id = uuid.uuid4()
        await _create_data_source(db_session, ds_id)
        # No tables / no columns.

        log_id = await run_learning(db_session, ds_id)
        log = await _fetch_log(db_session, log_id)

        assert log.columns_described == 0
        assert log.status == "failed"

    @pytest.mark.asyncio
    async def test_partial_success_reflects_real_coverage(self, db_session):
        """columns_described must equal the non-null semantic_description count.

        3 of 5 columns described (via L0 comments); the 2 null columns also
        carry null_ratio (structural stat) but must not be counted.
        """
        from learning.orchestrator import run_learning

        ds_id = uuid.uuid4()
        await _create_data_source(db_session, ds_id)
        await _create_table_with_columns(
            db_session,
            ds_id,
            columns=[
                {"name": "status", "comment": "状态"},
                {"name": "amount", "comment": "金额"},
                {"name": "created", "comment": "创建时间"},
                {"name": "usr_typ_cd", "null_ratio": 0.5},
                {"name": "qwxz_foo", "null_ratio": 0.0},
            ],
        )

        log_id = await run_learning(db_session, ds_id)
        log = await _fetch_log(db_session, log_id)

        assert log.columns_described == 3  # 3/5 = 0.6
        assert log.status == "partial_success"

    @pytest.mark.asyncio
    async def test_success_when_fully_covered(self, db_session):
        """All columns described → success."""
        from learning.orchestrator import run_learning

        ds_id = uuid.uuid4()
        await _create_data_source(db_session, ds_id)
        await _create_table_with_columns(
            db_session,
            ds_id,
            columns=[
                {"name": "a", "comment": "列A"},
                {"name": "b", "comment": "列B"},
                {"name": "c", "comment": "列C"},
            ],
        )

        log_id = await run_learning(db_session, ds_id)
        log = await _fetch_log(db_session, log_id)

        assert log.columns_described == 3  # 3/3 = 1.0
        assert log.status == "success"
