"""Knowledge-base lifecycle — refresh after learning + cleanup on data-source deletion.

Refresh builds the vector index and the graph for the active data source. Vector
build is non-fatal (embedding service may be flaky): a failure is logged and the
graph still builds; the failed columns retry on the next learning run. Cleanup
removes a data source's records from Milvus and Neo4j (the app DB's CASCADE does
not reach the external stores).
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from knowledge.embedding import EmbeddingClient
from knowledge.graph_store import GraphStore, build_graph
from knowledge.vector_store import VectorStore, build_field_vectors

logger = logging.getLogger(__name__)


async def refresh_knowledge_base(
    session: AsyncSession,
    data_source_id: uuid.UUID,
    *,
    vector_store: VectorStore,
    graph_store: GraphStore,
    embedding_client: EmbeddingClient,
) -> None:
    """Refresh the knowledge base for a data source (active sources only).

    Vector build failure is suppressed + logged (graph still builds); the whole
    call never raises so callers can wrap it in a single ``suppress(Exception)``.
    """
    from config.data_source_model import DataSource

    ds_result = await session.execute(select(DataSource).where(DataSource.id == data_source_id))
    ds = ds_result.scalar_one_or_none()
    if ds is None or not ds.is_active:
        return

    try:
        await build_field_vectors(
            session,
            data_source_id,
            embedding_client=embedding_client,
            vector_store=vector_store,
        )
    except Exception as exc:  # noqa: BLE001 — non-fatal: graph still builds, retry next run
        logger.warning("knowledge: vector refresh failed for %s: %s", data_source_id, exc)

    await build_graph(session, data_source_id, graph_store=graph_store)


async def cleanup_knowledge_base(
    data_source_id: uuid.UUID,
    *,
    vector_store: VectorStore,
    graph_store: GraphStore,
) -> None:
    """Delete a data source's records from Milvus and Neo4j (on data-source deletion)."""
    try:
        vector_store.delete_by_data_source(str(data_source_id))
    except Exception as exc:  # noqa: BLE001 — cleanup best-effort
        logger.warning("knowledge: vector cleanup failed for %s: %s", data_source_id, exc)
    try:
        graph_store.delete_by_data_source(data_source_id)
    except Exception as exc:  # noqa: BLE001 — cleanup best-effort
        logger.warning("knowledge: graph cleanup failed for %s: %s", data_source_id, exc)
