"""Cross-table field self-healing — vector search + graph JOIN. (issue #43)"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

SCORE_THRESHOLD = 0.7


async def heal_cross_table(
    missing_column: str,
    current_table: str,
    data_source_id: Any,
    *,
    vector_search: Any = None,
    graph_store: Any = None,
) -> dict[str, Any] | None:
    """Try to find *missing_column* in a related table via vector + graph JOIN.

    Returns ``{candidate_table, candidate_column, join_path}`` or None.
    """
    if vector_search is None or graph_store is None:
        return None

    # 1. vector global search
    try:
        hits = await vector_search(missing_column, data_source_id)
    except Exception as e:
        logger.warning("cross-table vector search failed: %s", e)
        return None

    # 2. filter: other tables only, score > threshold
    candidates = [h for h in hits if h.get("table") != current_table and h.get("score", 0) > SCORE_THRESHOLD]
    if not candidates:
        return None

    # 3. for each candidate, try graph JOIN path
    from knowledge.graph_query import shortest_join_path
    for c in candidates:
        try:
            path = await shortest_join_path(graph_store, data_source_id, current_table, c["table"])
            if path:
                return {
                    "candidate_table": c["table"],
                    "candidate_column": c.get("column", missing_column),
                    "join_path": path,
                }
        except Exception as e:
            logger.warning("cross-table graph query failed for %s->%s: %s", current_table, c["table"], e)
    return None
