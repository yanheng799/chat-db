"""Error learning loop — healing_records storage + Phase 3 feedback. (issue #44)"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def record_healing(
    session: AsyncSession,
    *,
    error_type: str,
    original_sql: str,
    fix_type: str,
    fix_sql: str | None,
    success: bool,
) -> None:
    """Append a healing attempt record. Best-effort (never raises)."""
    try:
        await session.execute(
            text(
                "INSERT INTO healing_records (id, error_type, original_sql, fix_type, fix_sql, success, created_at) "
                "VALUES (:id, :et, :osql, :ft, :fsql, :ok, :now)"
            ),
            {
                "id": uuid.uuid4(),
                "et": error_type,
                "osql": original_sql,
                "ft": fix_type,
                "fsql": fix_sql,
                "ok": success,
                "now": datetime.now(),
            },
        )
        await session.commit()
    except Exception as e:
        logger.warning("failed to record healing: %s", e)


async def feedback_to_phase3(
    session: AsyncSession,
    data_source_id: Any,
    fix_type: str,
) -> None:
    """Feedback a successful healing to Phase 3 knowledge base. Best-effort."""
    if fix_type != "metadata_sync":
        return
    try:
        from knowledge.embedding import EmbeddingClient
        from knowledge.graph_store import GraphStore, build_graph
        from knowledge.vector_store import VectorStore, build_field_vectors

        vec = VectorStore()
        graph = GraphStore()
        emb = EmbeddingClient()
        await build_field_vectors(session, data_source_id, embedding_client=emb, vector_store=vec)
        await build_graph(session, data_source_id, graph_store=graph)
    except Exception as e:
        logger.warning("healing feedback to Phase 3 failed: %s", e)
