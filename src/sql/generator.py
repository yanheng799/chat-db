"""Single-step SQL generator — LLM prompt with schema + constraints. (issue #32)"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_SCHEMA_PROMPT_TMPL = """你是一个数据库查询 SQL 生成助手。根据以下信息生成一条只读 SQL 查询。

已知表结构（优先参考）：
{schema_desc}

{join_paths}

查询约束（必须遵守）：
- 只生成 SELECT 语句
- 必须包含 LIMIT 子句，且 LIMIT ≤ 1000
- 禁止 SELECT *
- 最多 JOIN 4 张额外表（共 5 张表以内），禁止子查询、UNION、CTE
- 如果提供了 JOIN 路径，必须使用提供的路径编写 ON 条件
- 尽量使用已知表结构中的表名，但如果用户查询中提到的表名不在已知结构中，也可以凭经验推断
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
    join_paths: list[dict[str, Any]] | None = None,
) -> str | None:
    """Generate a single-step SELECT statement via LLM. Returns SQL string or None."""
    norm_parts = []
    for nv in normalized_values:
        if nv.get("db_representation"):
            norm_parts.append(str(nv["db_representation"]))

    # Format JOIN paths for prompt
    join_section = ""
    if join_paths:
        paths_formatted = []
        for p in join_paths:
            conf = f", confidence={p.get('confidence', 0):.0%}" if p.get('confidence') else ""
            paths_formatted.append(
                f"  {p['from_table']}.{p['from_column']} → {p['to_table']}.{p['to_column']}"
                f" ({p.get('type', 'FK')}{conf})"
            )
        join_section = "可用的 JOIN 路径（必须使用这些路径编写 ON 条件）:\n" + "\n".join(paths_formatted)
    else:
        join_section = "（无预定义 JOIN 路径，可自行推断表间关联）"

    prompt = _SCHEMA_PROMPT_TMPL.format(
        schema_desc=schema_desc,
        join_paths=join_section,
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
