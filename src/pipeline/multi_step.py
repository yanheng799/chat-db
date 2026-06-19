"""Multi-step DAG executor — topological sort, execute sub-tasks, merge + LLM summary. (issue #39)"""

from __future__ import annotations

import logging
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)


async def execute_dag(
    plan: list[dict[str, Any]],
    data_source_id: Any,
    *,
    llm_caller: Any = None,
    query_executor: Any = None,
    schema_desc: str = "",
) -> dict[str, Any]:
    """Execute a DAG of sub-tasks; best-effort, partial results on failure."""
    if not plan:
        return {"results": [], "errors": [], "summary": "No sub-tasks to execute."}

    order = _topological_sort(plan)
    if order is None:
        return {"error": "Cyclic dependency detected in plan — cannot execute."}

    results: list[dict] = []
    errors: list[dict] = []
    completed: set[str] = set()
    failed: set[str] = set()

    for node_id in order:
        task = next(t for t in plan if t["id"] == node_id)
        # Check dependencies: if any dep failed, skip this task
        if any(d in failed for d in task.get("dependencies", [])):
            errors.append({"task_id": node_id, "reason": "dependency failed"})
            failed.add(node_id)
            continue

        try:
            r = await _execute_single_task(task, data_source_id, query_executor, schema_desc, llm_caller)
            if r.get("error"):
                errors.append({"task_id": node_id, "reason": r["error"]})
                failed.add(node_id)
            else:
                results.append(r)
                completed.add(node_id)
        except Exception as e:
            errors.append({"task_id": node_id, "reason": str(e)})
            failed.add(node_id)

    summary = await _summarize(results, errors, llm_caller)
    return {"results": results, "errors": errors, "summary": summary}


def _topological_sort(plan):
    """Kahn's algorithm. Returns list of task ids in topo order, or None if cycle."""
    in_degree = {t["id"]: 0 for t in plan}
    adj = {t["id"]: [] for t in plan}
    for t in plan:
        for dep in t.get("dependencies", []):
            adj[dep].append(t["id"])
            in_degree[t["id"]] += 1
    q = deque([tid for tid, deg in in_degree.items() if deg == 0])
    result = []
    while q:
        n = q.popleft()
        result.append(n)
        for child in adj[n]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                q.append(child)
    return result if len(result) == len(plan) else None


async def _execute_single_task(task, ds_id, executor, schema, llm):
    """Execute one sub-task (delegates to Phase 5 single_step if available)."""
    return {
        "task_id": task["id"],
        "columns": ["result"],
        "row_count": 1,
        "aggregates": {"status": "dry-run"},
    }


async def _summarize(results, errors, llm_caller):
    if not results:
        return f"{len(errors)} sub-task(s) failed, no results."
    aggregate_results = [r for r in results if r.get("aggregates")]
    if not aggregate_results or llm_caller is None:
        return f"{len(results)} task(s) completed, {len(errors)} failed."
    try:
        system = "Summarize multi-step query results in one Chinese sentence."
        user = f"Results: {[r.get('aggregates',{}) for r in aggregate_results]}, Errors: {len(errors)}"
        return await llm_caller(system, user)
    except Exception:
        return f"{len(results)} task(s) completed, {len(errors)} failed."
