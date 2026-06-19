"""LangGraph state graph — single/multi-step routing (Phase 6 / issue #37)."""

from __future__ import annotations

import logging
import re
from typing import Any, Literal

from langgraph.graph import StateGraph, END

from agents.state import PipelineState

logger = logging.getLogger(__name__)

MULTI_STEP_PATTERNS: list[tuple[str, str]] = [
    (r"对比|比较|变化|差异|环比|同比", "comparison"),
    (r"先.*再|然后|最后|第.*步", "sequential_steps"),
    (r"同时查|分别查", "parallel_queries"),
]


def classify_query(state: PipelineState) -> dict[str, Any]:
    """Rule-based routing: multi-step patterns + graph join detection."""
    text = state.get("nl_text", "")
    # 1. regex patterns
    for pattern, reason in MULTI_STEP_PATTERNS:
        if re.search(pattern, text):
            return {"route": "multi"}

    # 2. graph join detection: >1 table matched → check join path
    fields = state.get("matched_fields", [])
    tables = list({f["table"] for f in fields if f.get("table")})
    if len(tables) > 1:
        return {"route": "multi"}

    return {"route": "single"}


async def run_single_step_node(state: PipelineState) -> dict[str, Any]:
    """Delegate to Phase 5 single-step pipeline."""
    from pipeline.single_step import run_single_step

    result = await run_single_step(
        state.get("nl_text", ""),
        state.get("data_source_id", ""),
    )
    if result.get("error"):
        return {"error": result["error"]}
    return {
        "results": [result.get("result")],
        "summary": result.get("summary", ""),
        "need_confirm_items": result.get("need_confirm_items", []),
    }


async def plan_generation_node(state: PipelineState) -> dict[str, Any]:
    """Generate multi-step plan (placeholder — implemented in #38)."""
    # For #37, return empty plan to show routing works
    return {"plan": [], "route": "multi"}


async def multi_step_executor_node(state: PipelineState) -> dict[str, Any]:
    """Execute multi-step DAG (placeholder — implemented in #39)."""
    return {"summary": "(multi-step execution pending)", "results": []}


def build_graph() -> StateGraph:
    """Construct the LangGraph state graph for single/multi-step routing."""
    workflow = StateGraph(PipelineState)

    workflow.add_node("classify_query", classify_query)
    workflow.add_node("run_single_step", run_single_step_node)
    workflow.add_node("plan_generation", plan_generation_node)
    workflow.add_node("multi_step_executor", multi_step_executor_node)

    workflow.set_entry_point("classify_query")

    workflow.add_conditional_edges(
        "classify_query",
        lambda s: "multi" if s.get("route") == "multi" else "single",
        {"single": "run_single_step", "multi": "plan_generation"},
    )
    workflow.add_edge("run_single_step", END)
    workflow.add_edge("plan_generation", "multi_step_executor")
    workflow.add_edge("multi_step_executor", END)

    return workflow.compile()
