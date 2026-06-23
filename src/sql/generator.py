"""Single-step SQL generator — LLM prompt with schema + constraints. (issue #32)"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)
# _log = logging.getLogger("uvicorn.error")

_SCHEMA_PROMPT_TMPL = """你是一个 PostgreSQL 只读查询 SQL 生成助手。请根据以下信息生成一条正确的 SELECT 语句。

已知表结构（优先参考）：
{schema_desc}

{join_paths}

【查询约束 — 必须全部遵守】
1. 只生成一条 SELECT 语句：禁止 INSERT/UPDATE/DELETE/DDL，禁止子查询、UNION、CTE，禁止 SELECT *。
2. 必须以 LIMIT 子句结尾，且 LIMIT ≤ 1000。
3. FROM 与 JOIN 合计不超过 5 张表（即最多额外 JOIN 4 张）。
4. 若提供了 JOIN 路径，必须按这些路径编写 ON 条件。
5. 优先使用「已知表结构」中的表名；仅当用户明确提到且结构中确实缺失该表时，才可凭经验补全表名。

【表别名规范 — 极其重要，违反将直接导致 SQL 报错】
- 在 FROM / JOIN 中为表定义别名后（例如 `rag_datasets AS ds`），整条 SQL 其余位置
  （SELECT / WHERE / GROUP BY / HAVING / ORDER BY / ON）引用该表的列时，必须使用
  同一个别名 `ds`，不得对该表换用任何其它别名。
- 严禁对同一张表使用两个不同别名；严禁引用未在 FROM / JOIN 中定义过的别名。
- 单表查询可不使用别名，直接写 `表名.列名`，避免别名混淆。
- 使用聚合函数（COUNT/SUM/AVG/MAX/MIN）时，SELECT 中的非聚合列必须同时出现在
  GROUP BY 中，且使用相同的表别名。

  正确示例：
    SELECT ds.dataset_id, ds.name, COUNT(doc.doc_id) AS cnt
    FROM rag_datasets AS ds
    LEFT JOIN rag_documents AS doc ON ds.dataset_id = doc.dataset_id
    GROUP BY ds.dataset_id, ds.name
  错误示例：FROM rag_datasets AS ds ... GROUP BY d.dataset_id
    ← 别名 "d" 从未定义，应为 "ds"

用户查询：{nl_text}
语义匹配字段（表名.列名，请使用这些列）：{matched_fields}
标准化值（SQL 片段，直接嵌入 WHERE / ON）：{norm_values}

只输出 SQL 语句本身，不要输出任何解释、说明或注释。"""


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
            conf = f", confidence={p.get('confidence', 0):.0%}" if p.get("confidence") else ""
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
    logger.info("sql-gen: system=%r", system)
    logger.info("sql-gen: user_prompt=%s", prompt[:500])
    try:
        response = await llm_caller(system, prompt)
        logger.info("sql-gen: response=%s", response[:500])
        return _extract_sql(response)
    except Exception as e:
        logger.warning("SQL generation failed: %s", e)
        return None


def _format_matches(fields):
    return ", ".join(f"{f['table']}.{f['column']}" for f in fields if f.get("table") and f.get("column"))


def _extract_sql(text):
    """Extract SQL from LLM response (strip markdown fences, return first SELECT statement)."""
    text = re.sub(r"^```(?:sql)?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text.strip())
    m = re.search(r"(?i)\bSELECT\b.+", text, re.DOTALL)
    return m.group(0).rstrip(";").strip() if m else None
