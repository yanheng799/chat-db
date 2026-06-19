"""Tests for knowledge-base lifecycle — refresh + cleanup (issue #21 / 004)."""

import uuid

import pytest

from knowledge.lifecycle import cleanup_knowledge_base, refresh_knowledge_base
from test_knowledge.test_vector_store import _add_table_with_columns, _create_data_source


async def _create_active_data_source(session, ds_id):
    from config.data_source_model import DataSource
    from config.encryption import encrypt_value, generate_fernet_key

    key = generate_fernet_key()
    session.add(
        DataSource(
            id=ds_id,
            name=f"act-{ds_id.hex[:8]}",
            engine="postgresql",
            host="localhost",
            port=5432,
            username="test",
            password_encrypted=encrypt_value("test", key),
            database="testdb",
            is_active=True,
        )
    )
    await session.commit()


def _raising_embed(*_args, **_kwargs):
    raise RuntimeError("embedding service down")


@pytest.mark.asyncio
async def test_refresh_builds_vector_and_graph(db_session, milvus_store, neo4j_store, embedding_client):
    ds_id = uuid.uuid4()
    await _create_active_data_source(db_session, ds_id)
    await _add_table_with_columns(
        db_session,
        ds_id,
        "orders",
        columns=[
            {"name": "status", "type": "varchar", "desc": "订单状态", "source": "rule_inference", "confidence": 0.7}
        ],
    )

    await refresh_knowledge_base(
        db_session,
        ds_id,
        vector_store=milvus_store,
        graph_store=neo4j_store,
        embedding_client=embedding_client,
    )

    assert milvus_store.list_embed_texts(str(ds_id))  # vector stored
    assert neo4j_store.count_nodes(ds_id, "Table") == 1


@pytest.mark.asyncio
async def test_refresh_non_fatal_on_vector_failure(
    db_session, milvus_store, neo4j_store, embedding_client, monkeypatch
):
    ds_id = uuid.uuid4()
    await _create_active_data_source(db_session, ds_id)
    await _add_table_with_columns(
        db_session,
        ds_id,
        "orders",
        columns=[{"name": "status", "type": "varchar", "desc": "订单状态"}],
    )
    monkeypatch.setattr(embedding_client, "embed_sync", _raising_embed)

    # Must not raise; graph still builds even though embedding fails.
    await refresh_knowledge_base(
        db_session,
        ds_id,
        vector_store=milvus_store,
        graph_store=neo4j_store,
        embedding_client=embedding_client,
    )

    assert milvus_store.list_embed_texts(str(ds_id)) == {}  # vector build failed
    assert neo4j_store.count_nodes(ds_id, "Table") == 1  # graph built anyway


@pytest.mark.asyncio
async def test_refresh_skips_inactive_data_source(db_session, milvus_store, neo4j_store, embedding_client):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)  # inactive by default
    await _add_table_with_columns(
        db_session, ds_id, "orders", columns=[{"name": "status", "type": "varchar", "desc": "订单状态"}]
    )

    await refresh_knowledge_base(
        db_session,
        ds_id,
        vector_store=milvus_store,
        graph_store=neo4j_store,
        embedding_client=embedding_client,
    )

    assert milvus_store.list_embed_texts(str(ds_id)) == {}
    assert neo4j_store.count_nodes(ds_id) == 0


@pytest.mark.asyncio
async def test_cleanup_removes_both_stores(db_session, milvus_store, neo4j_store, embedding_client):
    ds_id = uuid.uuid4()
    await _create_active_data_source(db_session, ds_id)
    await _add_table_with_columns(
        db_session, ds_id, "orders", columns=[{"name": "status", "type": "varchar", "desc": "订单状态"}]
    )
    await refresh_knowledge_base(
        db_session,
        ds_id,
        vector_store=milvus_store,
        graph_store=neo4j_store,
        embedding_client=embedding_client,
    )
    assert milvus_store.list_embed_texts(str(ds_id))
    assert neo4j_store.count_nodes(ds_id) > 0

    await cleanup_knowledge_base(ds_id, vector_store=milvus_store, graph_store=neo4j_store)

    assert milvus_store.list_embed_texts(str(ds_id)) == {}
    assert neo4j_store.count_nodes(ds_id) == 0


@pytest.mark.asyncio
async def test_run_learning_invokes_knowledge_refresh(db_session, monkeypatch):
    """run_learning must call the knowledge-refresh step (non-fatal wiring)."""
    from learning import orchestrator

    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)  # inactive is fine for this wiring test
    await _add_table_with_columns(db_session, ds_id, "orders", columns=[{"name": "status", "type": "varchar"}])

    calls = []

    async def spy(session, data_source_id):
        calls.append(data_source_id)

    monkeypatch.setattr(orchestrator, "_refresh_knowledge_with_ds", spy)
    await orchestrator.run_learning(db_session, ds_id, trigger_type="manual")

    assert calls == [ds_id]
