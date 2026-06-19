"""Single-step SQL generator — LLM prompt with schema + constraints. (issue #32)"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_SCHEMA_PROMPT_TMPL = """你是一个数据库查询 SQL 生成助手。根据以下信息生成一条只读 SQL 查询。

表结构（仅可查询以下表/字段）：
{schema_desc}

查询约束（必须遵守）：
- 只生成 SELECT 语句
- 必须包含 LIMIT 子句，且 LIMIT ≤ 1000
- 禁止 SELECT *
- 只查询单张表（不要写 JOIN）
- 只输出 SQL 语句本身，不要输出解释或其他内容

用户查询：{nl_text}
语义匹配字段：{matched_fields}
标准化值（SQL 片段）：{norm_values}"""


async def generate_sql(
    nl_text: str,
    matched_fields: list[dict[str, Any]],
    normalized_values: list[dict[str, Any]],
    schema_desc: str,
    *,
    llm_caller: Any,
) -> str | None:
    """Generate a single-step SELECT statement via LLM. Returns SQL string or None."""
    norm_parts = []
    for nv in normalized_values:
        if nv.get("db_representation"):
            norm_parts.append(str(nv["db_representation"]))
    prompt = _SCHEMA_PROMPT_TMPL.format(
        schema_desc=schema_desc,
        nl_text=nl_text,
        matched_fields=_format_matches(matched_fields),
        norm_values=", ".join(norm_parts) if norm_parts else "（无）",
    )
    system = "你是一个 PostgreSQL SQL 生成器，只返回 SQL 语句。"
    try:
        response = await llm_caller(system, prompt)
        return _extract_sql(response)
    except Exception as e:
        logger.warning("SQL generation failed: %s", e)
        return None


def _format_matches(fields):
    return ", ".join(
        f"{f['table']}.{f['column']}" for f in fields if f.get("table") and f.get("column")
    )


def _extract_sql(text):
    """Extract SQL from LLM response (strip markdown fences, return first SELECT statement)."""
    text = re.sub(r"^```(?:sql)?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text.strip())
    m = re.search(r"(?i)\bSELECT\b.+", text, re.DOTALL)
    return m.group(0).rstrip(";").strip() if m else None
