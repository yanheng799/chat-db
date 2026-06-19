"""Multi-step plan generator — detect patterns, query graph, build DAG. (issue #38)"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

logger = logging.getLogger(__name__)

_COMPARISON = re.compile(r"对比|比较|变化|差异|环比|同比")
_SEQUENTIAL = re.compile(r"先.*再|然后|最后|第.*步")
_PARALLEL = re.compile(r"同时查|分别查")


async def generate_plan(
    nl_text: str,
    data_source_id: Any,
    matched_fields: list[dict[str, Any]],
    *,
    graph_store: Any = None,
) -> list[dict[str, Any]]:
    """Generate a DAG of sub-tasks from multi-step signals + graph join paths.

    Returns ``[{id, type, params, dependencies}]``.
    """
    plan: list[dict[str, Any]] = []

    # Detect multi-step type
    if _COMPARISON.search(nl_text):
        plan.extend(_comparison_plan(matched_fields))
    elif _SEQUENTIAL.search(nl_text):
        plan.extend(_sequential_plan(matched_fields))
    elif _PARALLEL.search(nl_text):
        plan.extend(_parallel_plan(matched_fields))
    else:
        plan.extend(_simple_multi_plan(matched_fields))

    # If multiple tables, query graph for JOIN paths
    tables = list({f["table"] for f in matched_fields if f.get("table")})
    if len(tables) > 1 and graph_store is not None:
        from knowledge.graph_query import shortest_join_path
        try:
            for i in range(len(tables) - 1):
                path = await shortest_join_path(graph_store, data_source_id, tables[i], tables[i + 1])
                if path:
                    plan.append({
                        "id": str(uuid.uuid4()),
                        "type": "join_path",
                        "params": {"path": path},
                        "dependencies": [],
                    })
        except Exception as e:
            logger.warning("graph join detection failed: %s", e)

    return plan


def _comparison_plan(fields):
    """Two time-window sub-queries in parallel."""
    return [
        {"id": str(uuid.uuid4()), "type": "sql_query", "params": {"description": "current_period", "fields": fields}, "dependencies": []},
        {"id": str(uuid.uuid4()), "type": "sql_query", "params": {"description": "previous_period", "fields": fields}, "dependencies": []},
    ]


def _sequential_plan(fields):
    """Sequential sub-tasks — each depends on the previous."""
    tasks = []
    for i in range(2):
        tasks.append({
            "id": str(uuid.uuid4()), "type": "sql_query", "params": {"description": f"step_{i+1}", "fields": fields},
            "dependencies": [tasks[-1]["id"]] if tasks else [],
        })
    return tasks


def _parallel_plan(fields):
    """Independent parallel sub-queries."""
    return [
        {"id": str(uuid.uuid4()), "type": "sql_query", "params": {"description": f"query_{i}", "fields": fields}, "dependencies": []}
        for i in range(2)
    ]


def _simple_multi_plan(fields):
    """Default: single sub-task wrapping all matched fields."""
    return [{"id": str(uuid.uuid4()), "type": "sql_query", "params": {"fields": fields}, "dependencies": []}]
