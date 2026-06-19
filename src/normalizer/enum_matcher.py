"""Enum value matcher — 5-strategy chain (issue #25)."""

from __future__ import annotations

import json
import logging
import re
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Any

from normalizer.mapping_service import list_enum_aliases
from normalizer.types import NormalizedValue

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_EDIT_THRESHOLD = 0.7
_LLM_CONFIDENCE_MIN = 0.85


async def normalize_enum(
    session: "AsyncSession",
    raw_value: str,
    data_source_id: Any,
    table_name: str,
    column_name: str,
    *,
    llm_caller: Any | None = None,
) -> NormalizedValue:
    """5-strategy enum normalizer: dict-lookup → display → alias → edit-distance → LLM."""
    text = raw_value.strip()
    rows = await list_enum_aliases(session, data_source_id)
    candidates = [r for r in rows if r["table_name"] == table_name and r["column_name"] == column_name]

    # Strategy 1–2: display exact match
    for r in candidates:
        if r["display"] == text:
            return _result(raw_value, r["value"], "display")

    # Strategy 3: alias match
    for r in candidates:
        aliases = r.get("aliases") or []
        if text in aliases:
            return _result(raw_value, r["value"], "alias")

    # Strategy 4: edit-distance fuzzy
    best = None
    best_score = 0.0
    for r in candidates:
        score = SequenceMatcher(None, text, r["display"]).ratio()
        if score > best_score:
            best_score = score
            best = r
    if best and best_score >= _EDIT_THRESHOLD:
        return _result(raw_value, best["value"], "edit_distance", confidence=best_score)

    # Strategy 5: LLM fallback
    if llm_caller is not None:
        known_values = [r["value"] for r in candidates]
        known_displays = [r["display"] for r in candidates]
        llm_result = await _try_llm(llm_caller, table_name, column_name, text, known_values, known_displays)
        if llm_result is not None:
            return llm_result

    # Only flag as need_confirm if there are known enum candidates to disambiguate
    need_confirm = len(candidates) > 0
    return NormalizedValue(
        original=raw_value, value_type="enum", need_confirm=need_confirm
    )


def _result(original, value, matched_by, confidence=1.0):
    return NormalizedValue(
        original=original,
        normalized=value,
        value_type="enum",
        db_representation=value,
        confidence=confidence,
        matched_by=matched_by,
    )


async def _try_llm(caller, table, column, user_input, values, displays):
    system = (
        "你是一个数据库枚举值匹配助手。你会收到字段名、已知枚举值列表和用户的口语输入。"
        "请判断用户说的值对应哪个枚举值。仅返回 JSON 格式："
        '{"value": "匹配的枚举值", "confidence": 0.95} '
        "或 {\"value\": null} 表示无法判断。"
        "不要返回其他内容。"
    )
    user_prompt = (
        f"表：{table}\n字段：{column}\n"
        f"已知枚举值：{values}\n已知展示名：{displays}\n"
        f"用户输入：{user_input}\n\n"
        f"请返回 JSON：{{\"value\": \"匹配的枚举值\", \"confidence\": 0.xx}} "
        f"或 {{\"value\": null}}"
    )
    try:
        response = await caller(system, user_prompt)
        response = re.sub(r"^```(?:json)?\s*\n?", "", response.strip())
        response = re.sub(r"\n?```\s*$", "", response.strip())
        parsed = json.loads(response)
        if not isinstance(parsed, dict) or not parsed.get("value"):
            return None
        confidence = float(parsed.get("confidence", 0))
        if confidence < _LLM_CONFIDENCE_MIN:
            return None
        return NormalizedValue(
            original=user_input,
            normalized=parsed["value"],
            value_type="enum",
            db_representation=parsed["value"],
            confidence=confidence,
            matched_by="llm",
        )
    except Exception:
        return None
