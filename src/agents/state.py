"""LangGraph state schema for multi-agent orchestration (Phase 6)."""

from __future__ import annotations

from typing import Any, TypedDict


class PipelineState(TypedDict, total=False):
    nl_text: str
    data_source_id: str
    route: str  # "single" | "multi"
    plan: list[dict[str, Any]]  # list of sub-tasks
    matched_fields: list[dict[str, Any]]
    results: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    summary: str
    need_confirm_items: list[dict[str, Any]]
    error: str
