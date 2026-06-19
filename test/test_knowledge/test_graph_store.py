"""Tests for the Neo4j knowledge graph build (issue #19 / 002)."""

import uuid

import pytest

from knowledge.graph_store import build_graph
from metadata.models import MetadataForeignKey, MetadataInferredForeignKey

# conftest helpers (vector-store tests) are reused for app-DB setup
from test_knowledge.test_vector_store import _add_table_with_columns, _create_data_source


async def _add_column(session, table_id, name, *, pk=False, dtype="integer"):
    """Append one more column to an existing table (for FK targets/sources)."""
    from metadata.models import MetadataColumn

    session.add(
        MetadataColumn(
            id=uuid.uuid4(),
            table_id=table_id,
            column_name=name,
            data_type=dtype,
            is_nullable=True,
            is_primary_key=pk,
            ordinal_position=999,
        )
    )
    await session.commit()


async def _setup_customers_orders(session, ds_id):
    """customers(id PK, name) + orders(customer_id), with explicit + inferred FK to customers.id."""
    customers_id = await _add_table_with_columns(
        session,
        ds_id,
        "customers",
        columns=[
            {"name": "id", "type": "integer", "desc": "标识"},
            {"name": "name", "type": "varchar", "desc": "名称"},
        ],
    )
    # mark customers.id as PK
    from sqlalchemy import select

    from metadata.models import MetadataColumn

    res = await session.execute(
        select(MetadataColumn).where(MetadataColumn.table_id == customers_id).where(MetadataColumn.column_name == "id")
    )
    res.scalar_one().is_primary_key = True
    await session.commit()

    orders_id = await _add_table_with_columns(
        session,
        ds_id,
        "orders",
        columns=[{"name": "customer_id", "type": "integer", "desc": "客户"}],
    )
    # explicit FK: orders.customer_id -> customers.id
    session.add(
        MetadataForeignKey(
            id=uuid.uuid4(),
            table_id=orders_id,
            constraint_name="fk_orders_customer",
            column_name="customer_id",
            target_schema="public",
            target_table="customers",
            target_column="id",
        )
    )
    # inferred FK (same pair) to exercise INFERRED_REF with a confidence value
    session.add(
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
    await session.commit()
    return customers_id, orders_id


@pytest.mark.asyncio
async def test_build_creates_nodes_and_edges(db_session, neo4j_store):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    await _setup_customers_orders(db_session, ds_id)

    await build_graph(db_session, ds_id, graph_store=neo4j_store)

    assert neo4j_store.count_nodes(ds_id, "Table") == 2  # customers, orders
    assert neo4j_store.count_nodes(ds_id, "Column") == 3  # id, name, customer_id
    assert neo4j_store.count_edges(ds_id, "CONTAINS") == 3
    assert neo4j_store.count_edges(ds_id, "REFERENCES") == 1  # orders.customer_id -> customers.id
    assert neo4j_store.count_edges(ds_id, "INFERRED_REF") == 1


@pytest.mark.asyncio
async def test_build_confidence_stored_on_edges(db_session, neo4j_store):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    await _setup_customers_orders(db_session, ds_id)
    await build_graph(db_session, ds_id, graph_store=neo4j_store)

    with neo4j_store._driver.session() as s:  # noqa: SLF001
        ref = s.run(
            "MATCH ({data_source_id:$ds})-[r:REFERENCES]->({data_source_id:$ds}) RETURN r.confidence AS c",
            ds=str(ds_id),
        ).single()
        inf = s.run(
            "MATCH ({data_source_id:$ds})-[r:INFERRED_REF]->({data_source_id:$ds}) RETURN r.confidence AS c",
            ds=str(ds_id),
        ).single()
    assert ref["c"] == 1.0
    assert inf["c"] == 0.65


@pytest.mark.asyncio
async def test_full_rebuild_replaces_previous(db_session, neo4j_store):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    await _setup_customers_orders(db_session, ds_id)
    await build_graph(db_session, ds_id, graph_store=neo4j_store)
    assert neo4j_store.count_nodes(ds_id, "Table") == 2

    # Rebuild: drop orders by removing it from app DB, then rebuild.
    from sqlalchemy import delete, select

    from metadata.models import MetadataColumn, MetadataForeignKey, MetadataTable

    orders = (
        await db_session.execute(
            select(MetadataTable)
            .where(MetadataTable.data_source_id == ds_id)
            .where(MetadataTable.table_name == "orders")
        )
    ).scalar_one()
    await db_session.execute(delete(MetadataForeignKey).where(MetadataForeignKey.table_id == orders.id))
    await db_session.execute(delete(MetadataColumn).where(MetadataColumn.table_id == orders.id))
    await db_session.execute(delete(MetadataTable).where(MetadataTable.id == orders.id))
    await db_session.execute(
        delete(MetadataInferredForeignKey).where(MetadataInferredForeignKey.data_source_id == ds_id)
    )
    await db_session.commit()

    await build_graph(db_session, ds_id, graph_store=neo4j_store)
    assert neo4j_store.count_nodes(ds_id, "Table") == 1  # only customers remains
    assert neo4j_store.count_nodes(ds_id, "Column") == 2
    assert neo4j_store.count_edges(ds_id, "REFERENCES") == 0  # no leftovers
    assert neo4j_store.count_edges(ds_id, "INFERRED_REF") == 0


@pytest.mark.asyncio
async def test_multi_source_isolation(db_session, neo4j_store):
    ds_a = uuid.uuid4()
    ds_b = uuid.uuid4()
    await _create_data_source(db_session, ds_a)
    await _create_data_source(db_session, ds_b)
    await _setup_customers_orders(db_session, ds_a)
    await _setup_customers_orders(db_session, ds_b)

    await build_graph(db_session, ds_a, graph_store=neo4j_store)
    await build_graph(db_session, ds_b, graph_store=neo4j_store)

    # Each source has its own 2 tables; no cross-source node sharing.
    assert neo4j_store.count_nodes(ds_a, "Table") == 2
    assert neo4j_store.count_nodes(ds_b, "Table") == 2
    # No edge should connect a node of ds_a to a node of ds_b.
    with neo4j_store._driver.session() as s:  # noqa: SLF001
        cross = s.run("MATCH (a)-[r]->(b) WHERE a.data_source_id <> b.data_source_id RETURN count(r) AS c").single()[
            "c"
        ]
    assert cross == 0


@pytest.mark.asyncio
async def test_delete_by_data_source(db_session, neo4j_store):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    await _setup_customers_orders(db_session, ds_id)
    await build_graph(db_session, ds_id, graph_store=neo4j_store)
    assert neo4j_store.count_nodes(ds_id) > 0

    neo4j_store.delete_by_data_source(ds_id)
    assert neo4j_store.count_nodes(ds_id) == 0
