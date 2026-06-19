"""4-layer semantic matcher: hot-word → industry → vector → LLM fallback. (issue #31)"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from semantic.hot_words import HOT_WORDS, INDUSTRY_TERMS

logger = logging.getLogger(__name__)


async def match_semantic(
    raw_text: str,
    data_source_id: Any,
    *,
    vector_search: Any | None = None,
    llm_caller: Any | None = None,
) -> list[dict[str, Any]]:
    """Match *raw_text* to table.column(s) via 4-layer chain. Layer hit → stop."""
    text = raw_text.strip()
    matches: list[dict[str, Any]] = []

    # Layer 1: hot-word exact match
    for term, entry in HOT_WORDS.items():
        if term in text:
            matches.append(_hot_word_match(term, entry))
    if matches:
        return matches

    # Layer 2: industry term translation → hot-word retry
    for iterm, hot_target in INDUSTRY_TERMS.items():
        if iterm.lower() in text.lower():
            if hot_target in HOT_WORDS:
                matches.append(_hot_word_match(hot_target, HOT_WORDS[hot_target]))
                return matches

    # Layer 3: vector search (Phase 3 field_descriptions)
    if vector_search is not None:
        try:
            vector_results = await vector_search(text, data_source_id)
            for r in vector_results[:3]:  # top-3
                if r.get("score", 0) > 0.5:
                    matches.append({
                        "table": r["table"], "column": r["column"],
                        "matched_by": "vector", "confidence": r["score"],
                        "need_confirm": False,
                    })
        except Exception as e:
            logger.warning("vector search failed, skipping layer 3: %s", e)
    if matches:
        return matches

    # Layer 4: LLM fallback
    if llm_caller is not None:
        llm_result = await _try_llm_match(llm_caller, text)
        if llm_result:
            return llm_result

    return matches


def _hot_word_match(term, entry):
    return {
        "table": entry.get("target_table", ""),
        "column": entry.get("target_column", ""),
        "formula": entry.get("formula"),
        "locked": entry.get("locked", False),
        "matched_by": "hot_word",
        "confidence": 1.0,
        "need_confirm": False,
    }


async def _try_llm_match(caller, text):
    system = (
        "你是一个数据库查询语义匹配助手。用户会输入自然语言查询，请从查询中提取字段映射。"
        "仅返回 JSON 数组，格式：[{\"table\":\"表名\",\"column\":\"列名\",\"confidence\":0.9}]。"
        "不要返回其他内容。"
    )
    prompt = f"用户查询：{text}"
    try:
        response = await caller(system, prompt)
        response = re.sub(r"^```(?:json)?\s*\n?", "", response.strip())
        response = re.sub(r"\n?```\s*$", "", response.strip())
        parsed = json.loads(response)
        if not isinstance(parsed, list):
            return None
        matches = []
        for item in parsed:
            if item.get("table") and item.get("column"):
                matches.append({
                    "table": item["table"], "column": item["column"],
                    "matched_by": "llm_fallback",
                    "confidence": float(item.get("confidence", 0.7)),
                    "need_confirm": True,
                })
        return matches if matches else None
    except Exception:
        return None
