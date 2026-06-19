"""L2 LLM semantic inference — structured-signal prompt and response parsing.

This module contains the components of L2:

- :class:`FieldSignal` — the structured signals available for one field
- :func:`build_llm_prompt` — constructs the LLM prompt from structured signals only
- :func:`parse_llm_response` — extracts column descriptions from LLM output
- :func:`call_llm_with_retry` — LLM invocation with 429 retry

Data-governance note (V1): L2 infers semantic descriptions from **structured
signals only** — field name, data type, L1 enum values, L0 comment and the L1
splitting result. No raw business-data rows are sent to the external LLM.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass
class FieldSignal:
    """Structured signals available for one field during L2 inference.

    None of these carry raw business-data values: ``enum_values`` are the
    de-duplicated enum candidates produced by L1 pattern detection (a small,
    low-cardinality set), and ``comment`` is the schema comment extracted by L0.
    """

    name: str
    data_type: str
    enum_values: list[str] | None = None
    comment: str | None = None
    split: str | None = None


# ---------------------------------------------------------------------------
# LLM prompt builder
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = """\
你是一个数据库元数据标注助手。用户会给你一张数据库表的字段及其结构化信号（字段名、数据类型、枚举值、库注释、拆词结果），请据此推断每个字段的中文语义描述。你不会收到、也不应依据任何业务数据行的具体取值。

要求：
1. 仅返回 JSON 格式，不要返回其他内容。
2. 格式为 {"columns": {"字段名": "语义描述"}}。
3. 语义描述应简洁准确，不超过 20 个汉字。
4. 如果无法判断某个字段，其值设为 null。"""


def _format_field(field_signal: FieldSignal) -> str:
    """Render one field's structured signals as a single prompt line."""
    parts = [f"字段名：{field_signal.name}", f"类型：{field_signal.data_type}"]
    if field_signal.enum_values:
        parts.append(f"枚举值：{', '.join(field_signal.enum_values)}")
    if field_signal.comment:
        parts.append(f"库注释：{field_signal.comment}")
    if field_signal.split:
        parts.append(f"拆词：{field_signal.split}")
    return " | ".join(parts)


def build_llm_prompt(table_name: str, fields: list[FieldSignal]) -> str:
    """Construct the user-message portion of the LLM prompt.

    The prompt contains only structured signals (field name, data type, L1 enum
    values, L0 comment, splitting result). No raw business-data rows are
    included.
    """
    field_lines = "\n".join(f"  - {_format_field(f)}" for f in fields)

    return (
        f"表名：{table_name}\n"
        f"需要推断语义描述的字段（仅结构化信号）：\n"
        f"{field_lines}\n\n"
        f"请仅依据以上结构化信号推断每个字段的中文语义描述，"
        f"不要依据任何业务数据行的具体取值。\n"
        f'请返回 JSON：{{"columns": {{"字段名": "语义描述", ...}}}}'
    )


def get_system_prompt() -> str:
    """Return the system prompt for LLM calls."""
    return _SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# LLM response parser
# ---------------------------------------------------------------------------


def parse_llm_response(response: str) -> dict[str, str]:
    """Parse the LLM response into a ``{field_name: description}`` dict.

    Handles:
    - Raw JSON ``{"columns": {"field": "desc"}}``
    - JSON wrapped in markdown fences (`` ```json … ``` ``)
    - JSON without ``columns`` key (treats top-level dict directly)
    - Malformed input → returns empty dict
    """
    if not response or not response.strip():
        return {}

    # Strip markdown fences
    text = response.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}

    if not isinstance(parsed, dict):
        return {}

    # Support {"columns": {...}} wrapper
    if "columns" in parsed:
        if isinstance(parsed["columns"], dict):
            return parsed["columns"]
        return {}

    # Fallback: treat top-level keys as field→description
    return parsed


# ---------------------------------------------------------------------------
# LLM call abstraction
# ---------------------------------------------------------------------------


class LLMCaller(Protocol):
    """Protocol for LLM call — accepts a prompt string, returns response."""

    async def __call__(self, system_prompt: str, user_prompt: str) -> str: ...


class RateLimitError(Exception):
    """Raised when the LLM API returns a 429 rate-limit response."""


# Exponential backoff delays for 429 retries
_RETRY_DELAYS = [2, 4, 8]
_MAX_RETRIES = 3


async def call_llm_with_retry(
    caller: LLMCaller,
    table_name: str,
    fields: list[FieldSignal],
) -> dict[str, str] | None:
    """Call the LLM with exponential-backoff retry on rate-limit errors.

    Returns a ``{field_name: description}`` dict, or ``None`` if the LLM
    call fails after all retries (including non-rate-limit errors).
    """
    system_prompt = get_system_prompt()
    user_prompt = build_llm_prompt(table_name, fields)

    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = await caller(system_prompt, user_prompt)
            return parse_llm_response(response)
        except RateLimitError:
            if attempt < _MAX_RETRIES:
                delay = _RETRY_DELAYS[attempt]
                logger.warning(
                    "Rate limited on table %s, retrying in %ds (attempt %d/%d)",
                    table_name,
                    delay,
                    attempt + 1,
                    _MAX_RETRIES,
                )
                await asyncio.sleep(delay)
        except Exception as e:
            logger.error("LLM call failed for table %s: %s", table_name, e)
            return None

    logger.error("LLM call for table %s failed after %d retries", table_name, _MAX_RETRIES)
    return None


# Re-export for backwards-compatible imports within the package
__all__ = [
    "FieldSignal",
    "LLMCaller",
    "RateLimitError",
    "build_llm_prompt",
    "call_llm_with_retry",
    "get_system_prompt",
    "parse_llm_response",
]
