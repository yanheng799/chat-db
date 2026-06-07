"""L2 LLM semantic inference — sample data, build prompts, parse responses.

This module contains the components of L2:

- :func:`build_sample_query` — builds a sampling query excluding BLOB types
- :func:`build_llm_prompt` — constructs the LLM prompt
- :func:`parse_llm_response` — extracts column descriptions from LLM output
- :func:`truncate_value` — truncates TEXT values at 200 characters
- :func:`call_llm_with_retry` — LLM invocation with 429 retry
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# Binary/large-object types to exclude from sampling
_BINARY_TYPES = frozenset(
    {
        "blob",
        "binary",
        "varbinary",
        "bytea",
        "longblob",
        "mediumblob",
        "tinyblob",
        "image",
        "oid",
    }
)

# Maximum TEXT value length before truncation
MAX_TEXT_LENGTH = 200


def is_binary_type(data_type: str) -> bool:
    """Return True if *data_type* is a binary/large-object SQL type."""
    return data_type.lower().split("(")[0].strip() in _BINARY_TYPES


def truncate_value(value: Any) -> Any:
    """Truncate string values exceeding :data:`MAX_TEXT_LENGTH` characters."""
    if value is None:
        return None
    if isinstance(value, str) and len(value) > MAX_TEXT_LENGTH:
        return value[:MAX_TEXT_LENGTH]
    return value


# ---------------------------------------------------------------------------
# Sample query builder
# ---------------------------------------------------------------------------


def build_sample_query(
    table_name: str,
    schema_name: str | None,
    columns: list[Any],
    engine_type: str,
) -> str | None:
    """Build a ``SELECT … LIMIT 5`` query, excluding BLOB-type columns.

    Returns ``None`` when no columns survive the BLOB filter (or when
    *columns* is empty).
    """
    safe_cols = [c for c in columns if not is_binary_type(c.data_type)]
    if not safe_cols:
        return None

    if engine_type == "postgresql":
        fqn = f'"{schema_name}"."{table_name}"' if schema_name else f'"{table_name}"'
        col_list = ", ".join(f'"{c.column_name}"' for c in safe_cols)
    else:
        fqn = f"`{table_name}`"
        col_list = ", ".join(f"`{c.column_name}`" for c in safe_cols)

    return f"SELECT {col_list} FROM {fqn} LIMIT 5"


# ---------------------------------------------------------------------------
# LLM prompt builder
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
你是一个数据库元数据标注助手。用户会给你一张数据库表的样本数据和需要推断的字段名列表。
请根据样本数据推断每个字段的中文语义描述。

要求：
1. 仅返回 JSON 格式，不要返回其他内容。
2. 格式为 {"columns": {"字段名": "语义描述"}}。
3. 语义描述应简洁准确，不超过 20 个汉字。
4. 不要记忆或输出样本中的具体数据值。
5. 如果无法判断某个字段，其值设为 null。"""


def build_llm_prompt(
    table_name: str,
    field_names: list[str],
    sample_rows: list[dict[str, Any]],
) -> str:
    """Construct the user-message portion of the LLM prompt.

    The prompt includes the table name, the list of fields to describe,
    and a few sample rows for context.
    """
    # Truncate sample values
    safe_rows = []
    for row in sample_rows:
        safe_row = {k: truncate_value(v) for k, v in row.items()}
        safe_rows.append(safe_row)

    rows_text = ""
    if safe_rows:
        rows_text = "\n样本数据（仅供参考，不要输出具体值）：\n"
        for row in safe_rows:
            rows_text += f"  {row}\n"
    else:
        rows_text = "\n（无样本数据）\n"

    return (
        f"表名：{table_name}\n"
        f"需要推断语义描述的字段：{field_names}"
        f"{rows_text}\n"
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
    field_names: list[str],
    sample_rows: list[dict[str, Any]],
) -> dict[str, str] | None:
    """Call the LLM with exponential-backoff retry on rate-limit errors.

    Returns a ``{field_name: description}`` dict, or ``None`` if the LLM
    call fails after all retries (including non-rate-limit errors).
    """
    system_prompt = get_system_prompt()
    user_prompt = build_llm_prompt(table_name, field_names, sample_rows)

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
