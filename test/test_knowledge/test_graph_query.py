"""Tests for Neo4j graph queries (issue #20 / 003)."""

import uuid

import pytest
from sqlalchemy import select

from knowledge.graph_query import related_tables, shortest_join_path
from knowledge.graph_store import build_graph
from metadata.models import MetadataColumn, MetadataForeignKey, MetadataInferredForeignKey
from test_knowledge.test_vector_store import _add_table_with_columns, _create_data_source


async def _mark_pk(session, table_id, column_name):
    res = await session.execute(
        select(MetadataColumn)
        .where(MetadataColumn.table_id == table_id)
        .where(MetadataColumn.column_name == column_name)
    )
    res.scalar_one().is_primary_key = True
    await session.commit()


async def _explicit_fk(session, src_table_id, src_col, tgt_table, tgt_col="id"):
    session.add(
        MetadataForeignKey(
            id=uuid.uuid4(),
            table_id=src_table_id,
            constraint_name=f"fk_{src_col}_{tgt_table}",
            column_name=src_col,
            target_schema="public",
            target_table=tgt_table,
            target_column=tgt_col,
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_shortest_path_direct_fk(db_session, neo4j_store):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    customers = await _add_table_with_columns(
        db_session, ds_id, "customers", columns=[{"name": "id", "type": "integer"}]
    )
    await _mark_pk(db_session, customers, "id")
    orders = await _add_table_with_columns(
        db_session, ds_id, "orders", columns=[{"name": "customer_id", "type": "integer"}]
    )
    await _explicit_fk(db_session, orders, "customer_id", "customers")
    await build_graph(db_session, ds_id, graph_store=neo4j_store)

    steps = await shortest_join_path(neo4j_store, ds_id, "orders", "customers")
    assert len(steps) == 1
    s = steps[0]
    assert s["from_table"] == "orders" and s["from_column"] == "customer_id"
    assert s["to_table"] == "customers" and s["to_column"] == "id"
    assert s["type"] == "REFERENCES"


@pytest.mark.asyncio
async def test_shortest_path_two_hops(db_session, neo4j_store):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    customers = await _add_table_with_columns(
        db_session, ds_id, "customers", columns=[{"name": "id", "type": "integer"}]
    )
    await _mark_pk(db_session, customers, "id")
    products = await _add_table_with_columns(
        db_session, ds_id, "products", columns=[{"name": "sku", "type": "varchar"}]
    )
    await _mark_pk(db_session, products, "sku")
    orders = await _add_table_with_columns(
        db_session,
        ds_id,
        "orders",
        columns=[
            {"name": "customer_id", "type": "integer"},
            {"name": "product_sku", "type": "varchar"},
        ],
    )
    await _explicit_fk(db_session, orders, "customer_id", "customers")
    await _explicit_fk(db_session, orders, "product_sku", "products", tgt_col="sku")
    await build_graph(db_session, ds_id, graph_store=neo4j_store)

    steps = await shortest_join_path(neo4j_store, ds_id, "customers", "products")
    assert len(steps) == 2  # via orders


@pytest.mark.asyncio
async def test_no_path_returns_empty(db_session, neo4j_store):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    await _add_table_with_columns(db_session, ds_id, "customers", columns=[{"name": "id", "type": "integer"}])
    await _add_table_with_columns(
        db_session, ds_id, "logs", columns=[{"name": "id", "type": "integer"}]
    )  # no FK to customers
    await build_graph(db_session, ds_id, graph_store=neo4j_store)

    assert await shortest_join_path(neo4j_store, ds_id, "customers", "logs") == []


@pytest.mark.asyncio
async def test_related_tables(db_session, neo4j_store):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    customers = await _add_table_with_columns(
        db_session, ds_id, "customers", columns=[{"name": "id", "type": "integer"}]
    )
    await _mark_pk(db_session, customers, "id")
    products = await _add_table_with_columns(
        db_session, ds_id, "products", columns=[{"name": "sku", "type": "varchar"}]
    )
    await _mark_pk(db_session, products, "sku")
    orders = await _add_table_with_columns(
        db_session,
        ds_id,
        "orders",
        columns=[
            {"name": "customer_id", "type": "integer"},
            {"name": "product_sku", "type": "varchar"},
        ],
    )
    await _explicit_fk(db_session, orders, "customer_id", "customers")
    await _explicit_fk(db_session, orders, "product_sku", "products", tgt_col="sku")
    await build_graph(db_session, ds_id, graph_store=neo4j_store)

    related = await related_tables(neo4j_store, ds_id, "orders")
    assert {r["table"] for r in related} == {"customers", "products"}


@pytest.mark.asyncio
async def test_confidence_filter_on_inferred_edge(db_session, neo4j_store):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    customers = await _add_table_with_columns(
        db_session, ds_id, "customers", columns=[{"name": "id", "type": "integer"}]
    )
    await _mark_pk(db_session, customers, "id")
    await _add_table_with_columns(db_session, ds_id, "orders", columns=[{"name": "customer_id", "type": "integer"}])
    # Only an INFERRED_REF edge (confidence 0.65) — no explicit FK.
    db_session.add(
        MetadataInferredForeignKey(
            data_source_id=ds_id,
            source_schema="public",
            source_table="orders",
            source_column="customer_id",
            target_schema="public",
            target_table="customers",
            target_column="id",
            overlap_rate=1.0,
            name_similarity=0.8,
            confidence=0.65,
            source="rule_inference",
        )
    )
    await db_session.commit()
    await build_graph(db_session, ds_id, graph_store=neo4j_store)

    assert len(await shortest_join_path(neo4j_store, ds_id, "orders", "customers")) == 1
    assert await shortest_join_path(neo4j_store, ds_id, "orders", "customers", min_confidence=0.8) == []
    assert len(await shortest_join_path(neo4j_store, ds_id, "orders", "customers", min_confidence=0.6)) == 1


@pytest.mark.asyncio
async def test_query_is_scoped_to_data_source(db_session, neo4j_store):
    ds_a = uuid.uuid4()
    ds_b = uuid.uuid4()
    await _create_data_source(db_session, ds_a)
    await _create_data_source(db_session, ds_b)
    for ds in (ds_a, ds_b):
        customers = await _add_table_with_columns(
            db_session, ds, "customers", columns=[{"name": "id", "type": "integer"}]
        )
        await _mark_pk(db_session, customers, "id")
        orders = await _add_table_with_columns(
            db_session, ds, "orders", columns=[{"name": "customer_id", "type": "integer"}]
        )
        await _explicit_fk(db_session, orders, "customer_id", "customers")
        await build_graph(db_session, ds, graph_store=neo4j_store)

    # Querying ds_a returns exactly one path; ds_b's nodes are out of scope.
    steps = await shortest_join_path(neo4j_store, ds_a, "orders", "customers")
    assert len(steps) == 1
