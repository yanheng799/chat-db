"""Tests for L1 value-overlap foreign-key inference (Issue 001)."""

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from learning.fk_inference import (
    DEFAULT_NAME_SIMILARITY_THRESHOLD,
    DISTINCT_VALUE_CAP,
    build_distinct_values_query,
    compute_name_similarity,
    compute_overlap_rate,
    confidence_for_overlap,
    generate_candidates,
    run_fk_inference,
)
from metadata.models import (
    MetadataColumn,
    MetadataIndex,
    MetadataInferredForeignKey,
    MetadataTable,
)

# ---------------------------------------------------------------------------
# Pure scoring helpers
# ---------------------------------------------------------------------------


class TestComputeNameSimilarity:
    def test_fk_column_matches_target_table(self):
        # customer_id echoes the referenced table "customers"
        sim = compute_name_similarity("customer_id", "id", "customers")
        assert sim >= 0.5

    def test_dissimilar_column_below_threshold(self):
        sim = compute_name_similarity("notes", "id", "customers")
        assert sim < DEFAULT_NAME_SIMILARITY_THRESHOLD

    def test_exact_column_match_is_high(self):
        sim = compute_name_similarity("user_id", "user_id", "users")
        assert sim >= 0.9


class TestComputeOverlapRate:
    def test_full_containment(self):
        assert compute_overlap_rate({1, 2, 3}, {1, 2, 3, 4}) == 1.0

    def test_partial_containment(self):
        assert compute_overlap_rate({1, 2, 5}, {1, 2, 3, 4}) == pytest.approx(2 / 3)

    def test_empty_source_is_zero(self):
        assert compute_overlap_rate(set(), {1, 2, 3}) == 0.0


class TestConfidenceForOverlap:
    def test_high_overlap(self):
        assert confidence_for_overlap(1.0) == 0.8
        assert confidence_for_overlap(0.95) == 0.8

    def test_mid_overlap(self):
        assert confidence_for_overlap(0.9) == 0.65
        assert confidence_for_overlap(0.8) == 0.65

    def test_below_threshold_is_none(self):
        assert confidence_for_overlap(0.79) is None
        assert confidence_for_overlap(0.0) is None


# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------


class TestBuildDistinctValuesQuery:
    def test_pg_no_sampling(self):
        sql = build_distinct_values_query("orders", "public", "customer_id", "postgresql", False)
        assert "SELECT DISTINCT" in sql
        assert '"customer_id"' in sql
        assert '"public"."orders"' in sql
        assert f"LIMIT {DISTINCT_VALUE_CAP}" in sql
        assert "TABLESAMPLE" not in sql

    def test_pg_sampling_for_large_table(self):
        sql = build_distinct_values_query("orders", "public", "customer_id", "postgresql", True)
        assert "TABLESAMPLE SYSTEM (1)" in sql
        assert f"LIMIT {DISTINCT_VALUE_CAP}" in sql

    def test_mysql_uses_backticks_and_limit(self):
        sql = build_distinct_values_query("orders", None, "customer_id", "mysql", False)
        assert "`customer_id`" in sql
        assert "`orders`" in sql
        assert f"LIMIT {DISTINCT_VALUE_CAP}" in sql


# ---------------------------------------------------------------------------
# Candidate generation (pure, in-memory objects)
# ---------------------------------------------------------------------------


def _col(table_id, name, dtype, pk=False):
    return SimpleNamespace(
        table_id=table_id, column_name=name, data_type=dtype, is_primary_key=pk
    )


def _table(name):
    return SimpleNamespace(id=uuid.uuid4(), table_name=name, schema_name="public")


def _idx(table_id, name, cols, unique):
    return SimpleNamespace(table_id=table_id, index_name=name, column_names=cols, is_unique=unique)


class TestGenerateCandidates:
    def test_pk_reference_generates_candidate(self):
        customers = _table("customers")
        orders = _table("orders")
        columns_by_table = {
            customers.id: [_col(customers.id, "id", "integer", pk=True), _col(customers.id, "name", "varchar")],
            orders.id: [_col(orders.id, "customer_id", "integer"), _col(orders.id, "notes", "text")],
        }
        candidates = generate_candidates([customers, orders], columns_by_table, {}, 0.5)
        assert len(candidates) == 1
        c = candidates[0]
        assert c.source_column.column_name == "customer_id"
        assert c.target_column.column_name == "id"
        assert c.target_table.table_name == "customers"
        assert c.name_similarity >= 0.5

    def test_unique_index_reference_generates_candidate(self):
        products = _table("products")
        orders = _table("orders")
        columns_by_table = {
            products.id: [_col(products.id, "sku", "varchar", pk=False)],
            orders.id: [_col(orders.id, "product_sku", "varchar")],
        }
        indexes_by_table = {products.id: [_idx(products.id, "uq_sku", ["sku"], True)]}
        candidates = generate_candidates([products, orders], columns_by_table, indexes_by_table, 0.5)
        # product_sku -> products.sku (unique, not PK) should be a candidate
        matches = [c for c in candidates if c.target_column.column_name == "sku"]
        assert len(matches) == 1

    def test_type_mismatch_excluded(self):
        customers = _table("customers")
        orders = _table("orders")
        columns_by_table = {
            customers.id: [_col(customers.id, "id", "integer", pk=True)],
            orders.id: [_col(orders.id, "customer_id", "varchar")],  # type mismatch
        }
        candidates = generate_candidates([customers, orders], columns_by_table, {}, 0.5)
        assert candidates == []

    def test_low_name_similarity_excluded(self):
        customers = _table("customers")
        orders = _table("orders")
        columns_by_table = {
            customers.id: [_col(customers.id, "id", "integer", pk=True)],
            orders.id: [_col(orders.id, "notes", "integer")],  # type ok, name dissimilar
        }
        candidates = generate_candidates([customers, orders], columns_by_table, {}, 0.5)
        assert candidates == []


# ---------------------------------------------------------------------------
# Integration: run_fk_inference with a mock executor + real DB session
# ---------------------------------------------------------------------------


async def _create_data_source(session, ds_id):
    from config.data_source_model import DataSource
    from config.encryption import encrypt_value, generate_fernet_key

    key = generate_fernet_key()
    session.add(
        DataSource(
            id=ds_id,
            name=f"fk-{ds_id.hex[:8]}",
            engine="postgresql",
            host="localhost",
            port=5432,
            username="test",
            password_encrypted=encrypt_value("test", key),
            database="testdb",
        )
    )
    await session.commit()


async def _add_table(session, ds_id, name, columns, indexes=None):
    table_id = uuid.uuid4()
    session.add(MetadataTable(id=table_id, data_source_id=ds_id, schema_name="public", table_name=name))
    await session.flush()
    for i, spec in enumerate(columns):
        session.add(
            MetadataColumn(
                id=uuid.uuid4(),
                table_id=table_id,
                column_name=spec["name"],
                data_type=spec["type"],
                is_nullable=True,
                is_primary_key=spec.get("pk", False),
                ordinal_position=i + 1,
            )
        )
    for spec in indexes or []:
        session.add(
            MetadataIndex(
                id=uuid.uuid4(),
                table_id=table_id,
                index_name=spec["name"],
                column_names=spec["cols"],
                is_unique=spec["unique"],
            )
        )
    await session.commit()
    return table_id


def _executor(returning: dict):
    """Build a mock executor keyed by table name + estimate detection.

    ``returning`` maps table_name -> list of distinct values; estimate queries
    return a small row count (no sampling).
    """

    async def _exec(sql: str):
        low = sql.lower()
        if "reltuples" in low or low.lstrip().startswith("explain"):
            return {"estimate": 1000}
        for table_name, values in returning.items():
            if table_name in low:
                return values
        return []

    return _exec


class TestRunFkInference:
    @pytest.mark.asyncio
    async def test_infers_fk_for_overlapping_pk_reference(self, db_session):
        ds_id = uuid.uuid4()
        await _create_data_source(db_session, ds_id)
        await _add_table(
            db_session, ds_id, "customers",
            columns=[{"name": "id", "type": "integer", "pk": True}, {"name": "name", "type": "varchar"}],
        )
        await _add_table(
            db_session, ds_id, "orders",
            columns=[{"name": "customer_id", "type": "integer"}, {"name": "notes", "type": "text"}],
        )

        executor = _executor({
            "orders": [1, 2, 3, 4, 5],         # orders.customer_id distinct values
            "customers": [1, 2, 3, 4, 5, 6, 7],  # customers.id distinct values
        })

        count = await run_fk_inference(db_session, ds_id, query_executor=executor, engine_type="postgresql")
        assert count == 1

        rows = (await db_session.execute(select(MetadataInferredForeignKey))).scalars().all()
        assert len(rows) == 1
        fk = rows[0]
        assert fk.source_table == "orders"
        assert fk.source_column == "customer_id"
        assert fk.target_table == "customers"
        assert fk.target_column == "id"
        assert fk.overlap_rate == 1.0
        assert fk.confidence == 0.8
        assert fk.source == "rule_inference"
        assert fk.name_similarity >= 0.5

    @pytest.mark.asyncio
    async def test_no_inference_when_overlap_below_threshold(self, db_session):
        ds_id = uuid.uuid4()
        await _create_data_source(db_session, ds_id)
        await _add_table(db_session, ds_id, "customers", columns=[{"name": "id", "type": "integer", "pk": True}])
        await _add_table(db_session, ds_id, "orders", columns=[{"name": "customer_id", "type": "integer"}])

        # overlap = 5/8 = 0.625 < 0.8
        executor = _executor({
            "orders": [1, 2, 3, 4, 5, 9, 10, 11],
            "customers": [1, 2, 3, 4, 5, 6, 7],
        })
        count = await run_fk_inference(db_session, ds_id, query_executor=executor)
        assert count == 0
        rows = (await db_session.execute(select(MetadataInferredForeignKey))).scalars().all()
        assert rows == []

    @pytest.mark.asyncio
    async def test_recompute_replace_clears_existing_inferred_fks(self, db_session):
        ds_id = uuid.uuid4()
        await _create_data_source(db_session, ds_id)
        await _add_table(db_session, ds_id, "customers", columns=[{"name": "id", "type": "integer", "pk": True}])
        await _add_table(db_session, ds_id, "orders", columns=[{"name": "customer_id", "type": "integer"}])

        # Pre-existing inferred FK (stale) for this data source.
        db_session.add(
            MetadataInferredForeignKey(
                data_source_id=ds_id,
                source_schema="public", source_table="orders", source_column="legacy_col",
                target_schema="public", target_table="customers", target_column="id",
                overlap_rate=0.5, name_similarity=0.5, confidence=0.65, source="rule_inference",
            )
        )
        await db_session.commit()

        executor = _executor({"orders": [1, 2, 3], "customers": [1, 2, 3, 4]})
        count = await run_fk_inference(db_session, ds_id, query_executor=executor)
        assert count == 1

        rows = (await db_session.execute(select(MetadataInferredForeignKey))).scalars().all()
        assert len(rows) == 1  # stale row replaced, not duplicated
        assert rows[0].source_column == "customer_id"

    @pytest.mark.asyncio
    async def test_overlap_query_failure_is_skipped(self, db_session):
        ds_id = uuid.uuid4()
        await _create_data_source(db_session, ds_id)
        await _add_table(db_session, ds_id, "customers", columns=[{"name": "id", "type": "integer", "pk": True}])
        await _add_table(db_session, ds_id, "orders", columns=[{"name": "customer_id", "type": "integer"}])

        async def failing_executor(sql: str):
            low = sql.lower()
            if "reltuples" in low:
                return {"estimate": 1000}
            raise RuntimeError("target DB unavailable")

        count = await run_fk_inference(db_session, ds_id, query_executor=failing_executor)
        assert count == 0  # no crash; candidate skipped
        rows = (await db_session.execute(select(MetadataInferredForeignKey))).scalars().all()
        assert rows == []
