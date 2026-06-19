"""Tests for the field_descriptions vector store (issue #18 / 001)."""

import uuid

import pytest
from sqlalchemy import select

from knowledge.vector_store import (
    build_field_text,
    build_field_vectors,
    compute_upsert_plan,
    search_fields,
)
from metadata.models import MetadataColumn, MetadataTable

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestBuildFieldText:
    def test_table_column_description_concatenation(self):
        assert build_field_text("orders", "status", "订单状态") == "orders.status：订单状态"

    def test_disambiguates_same_column_across_tables(self):
        a = build_field_text("orders", "status", "订单状态")
        b = build_field_text("customers", "status", "客户状态")
        assert a != b


class TestComputeUpsertPlan:
    def _item(self, cid, text):
        return {"column_id": cid, "embed_text": text}

    def test_new_items_included(self):
        plan = compute_upsert_plan([self._item("c1", "a"), self._item("c2", "b")], {})
        assert len(plan) == 2

    def test_unchanged_items_excluded(self):
        items = [self._item("c1", "a")]
        existing = {"c1": "a"}
        assert compute_upsert_plan(items, existing) == []

    def test_changed_items_included(self):
        items = [self._item("c1", "a-new")]
        existing = {"c1": "a-old"}
        assert len(compute_upsert_plan(items, existing)) == 1

    def test_mixed(self):
        items = [self._item("c1", "a"), self._item("c2", "b-new"), self._item("c3", "c")]
        existing = {"c1": "a", "c2": "b-old"}
        plan = compute_upsert_plan(items, existing)
        assert {p["column_id"] for p in plan} == {"c2", "c3"}


# ---------------------------------------------------------------------------
# Integration: real Milvus + real embedding service
# ---------------------------------------------------------------------------


async def _create_data_source(session, ds_id):
    from config.data_source_model import DataSource
    from config.encryption import encrypt_value, generate_fernet_key

    key = generate_fernet_key()
    session.add(
        DataSource(
            id=ds_id,
            name=f"kb-{ds_id.hex[:8]}",
            engine="postgresql",
            host="localhost",
            port=5432,
            username="test",
            password_encrypted=encrypt_value("test", key),
            database="testdb",
        )
    )
    await session.commit()


async def _add_table_with_columns(session, ds_id, table_name, columns):
    table_id = uuid.uuid4()
    session.add(MetadataTable(id=table_id, data_source_id=ds_id, schema_name="public", table_name=table_name))
    await session.flush()
    for i, spec in enumerate(columns):
        session.add(
            MetadataColumn(
                id=uuid.uuid4(),
                table_id=table_id,
                column_name=spec["name"],
                data_type=spec.get("type", "text"),
                is_nullable=True,
                ordinal_position=i + 1,
                semantic_description=spec.get("desc"),
                description_source=spec.get("source"),
                description_confidence=spec.get("confidence"),
            )
        )
    await session.commit()
    return table_id


@pytest.mark.asyncio
async def test_build_and_search_disambiguates_by_table(db_session, embedding_client, milvus_store):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    await _add_table_with_columns(
        db_session,
        ds_id,
        "orders",
        [{"name": "status", "desc": "订单状态", "source": "rule_inference", "confidence": 0.7}],
    )
    await _add_table_with_columns(
        db_session,
        ds_id,
        "customers",
        [{"name": "status", "desc": "客户状态", "source": "rule_inference", "confidence": 0.7}],
    )

    n = await build_field_vectors(db_session, ds_id, embedding_client=embedding_client, vector_store=milvus_store)
    assert n == 2  # both columns embedded on first build

    hits = await search_fields(
        "订单的状态",
        ds_id,
        embedding_client=embedding_client,
        vector_store=milvus_store,
        top_k=2,
    )
    assert hits, "expected at least one hit"
    # Table-column context must disambiguate: orders.status ranks above customers.status.
    top = hits[0]
    assert top["table"] == "orders"
    assert top["column"] == "status"
    assert top["description_source"] == "rule_inference"


@pytest.mark.asyncio
async def test_incremental_skips_unchanged_then_picks_up_changes(db_session, embedding_client, milvus_store):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    table_id = await _add_table_with_columns(
        db_session,
        ds_id,
        "orders",
        [
            {"name": "status", "desc": "订单状态", "source": "rule_inference", "confidence": 0.7},
            {"name": "amount", "desc": "金额", "source": "rule_inference", "confidence": 0.7},
        ],
    )

    first = await build_field_vectors(db_session, ds_id, embedding_client=embedding_client, vector_store=milvus_store)
    assert first == 2

    # No change → nothing re-embedded.
    second = await build_field_vectors(db_session, ds_id, embedding_client=embedding_client, vector_store=milvus_store)
    assert second == 0

    # Change one description → exactly one re-embedded.
    result = await db_session.execute(
        select(MetadataColumn).where(MetadataColumn.table_id == table_id).where(MetadataColumn.column_name == "status")
    )
    col = result.scalar_one()
    col.semantic_description = "订单当前状态"
    await db_session.commit()

    third = await build_field_vectors(db_session, ds_id, embedding_client=embedding_client, vector_store=milvus_store)
    assert third == 1


@pytest.mark.asyncio
async def test_uncovered_columns_not_indexed(db_session, embedding_client, milvus_store):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    await _add_table_with_columns(
        db_session,
        ds_id,
        "orders",
        [
            {"name": "status", "desc": "订单状态", "source": "rule_inference", "confidence": 0.7},
            {"name": "uncovered", "desc": None},  # no semantic_description
        ],
    )
    n = await build_field_vectors(db_session, ds_id, embedding_client=embedding_client, vector_store=milvus_store)
    assert n == 1  # only the covered column

    # And the uncovered column cannot be retrieved.
    hits = await search_fields(
        "uncovered",
        ds_id,
        embedding_client=embedding_client,
        vector_store=milvus_store,
    )
    assert all(h["column"] != "uncovered" for h in hits)


@pytest.mark.asyncio
async def test_search_filters_by_data_source(db_session, embedding_client, milvus_store):
    ds_a = uuid.uuid4()
    ds_b = uuid.uuid4()
    await _create_data_source(db_session, ds_a)
    await _create_data_source(db_session, ds_b)
    await _add_table_with_columns(
        db_session,
        ds_a,
        "orders",
        [{"name": "status", "desc": "订单状态", "source": "rule_inference", "confidence": 0.7}],
    )
    await _add_table_with_columns(
        db_session,
        ds_b,
        "orders",
        [{"name": "status", "desc": "订单状态", "source": "rule_inference", "confidence": 0.7}],
    )
    await build_field_vectors(db_session, ds_a, embedding_client=embedding_client, vector_store=milvus_store)
    await build_field_vectors(db_session, ds_b, embedding_client=embedding_client, vector_store=milvus_store)

    # Searching ds_a only returns ds_a's record (payload carries its data_source_id).
    hits = await search_fields("订单状态", ds_a, embedding_client=embedding_client, vector_store=milvus_store)
    assert hits
    assert all(h["data_source_id"] == str(ds_a) for h in hits)


@pytest.mark.asyncio
async def test_delete_by_data_source(db_session, embedding_client, milvus_store):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    await _add_table_with_columns(
        db_session,
        ds_id,
        "orders",
        [{"name": "status", "desc": "订单状态", "source": "rule_inference", "confidence": 0.7}],
    )
    await build_field_vectors(db_session, ds_id, embedding_client=embedding_client, vector_store=milvus_store)
    assert milvus_store.list_embed_texts(str(ds_id))  # has the record

    milvus_store.delete_by_data_source(str(ds_id))
    assert milvus_store.list_embed_texts(str(ds_id)) == {}  # cleaned
