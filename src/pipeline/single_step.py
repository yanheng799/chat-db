"""Single-step query pipeline orchestrator (Phase 5 / issue #35).

Ties together time parsing → semantic matching → value normalization →
SQL generation → security validation → audit → execution → result summary.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MAX_LLM_CALLS = 5


async def run_single_step(
    nl_text: str,
    data_source_id: Any,
    *,
    session: Any = None,
    llm_caller: Any = None,
    vector_search: Any = None,
    query_executor: Any = None,
    schema_desc: str = "",
    max_llm_calls: int = DEFAULT_MAX_LLM_CALLS,
) -> dict[str, Any]:
    """Run a full single-step query pipeline. Returns {result, need_confirm_items, error}."""
    llm_calls = 0
    need_confirm_list: list[dict] = []

    def _llm_call(system, user):
        nonlocal llm_calls
        if llm_calls >= max_llm_calls:
            raise RuntimeError(f"LLM call limit ({max_llm_calls}) reached")
        llm_calls += 1
        return llm_caller(system, user)

    # 1. Time pre-normalization
    norm_values = []
    try:
        from normalizer.time_parser import parse_time
        tv = parse_time(nl_text)
        if not tv.need_confirm:
            norm_values.append({"db_representation": tv.db_representation})
    except Exception as e:
        logger.warning("time parse failed: %s", e)

    # 2. Semantic matching
    try:
        from semantic.matcher import match_semantic
        matches = await match_semantic(
            nl_text, data_source_id,
            vector_search=vector_search,
            llm_caller=_llm_call if llm_caller else None,
        )
    except Exception as e:
        logger.warning("semantic match failed: %s", e)
        return {"error": f"Semantic matching failed: {e}"}

    if not matches:
        return {"error": "Unable to understand query — no fields matched.", "need_confirm_items": []}

    for m in matches:
        if m.get("need_confirm"):
            need_confirm_list.append(m)

    # 3. Post-normalization (enum/region/name for each matched field)
    if session is not None:
        for m in matches:
            table = m.get("table", "")
            column = m.get("column", "")
            if not table or not column:
                continue
            try:
                from normalizer.enum_matcher import normalize_enum
                ev = await normalize_enum(session, nl_text, data_source_id, table, column,
                                          llm_caller=_llm_call if llm_caller else None)
                if ev.db_representation:
                    norm_values.append({"db_representation": f"{table}.{column}={ev.db_representation}"})
                if ev.need_confirm:
                    need_confirm_list.append({"field": f"{table}.{column}", "reason": "enum", "value": nl_text})
            except Exception:
                pass

    # 4. Quantifier check
    try:
        from normalizer.quantifier import detect_quantifier
        qv = detect_quantifier(nl_text)
        if qv.need_confirm:
            need_confirm_list.append({"reason": "quantifier", "value": nl_text})
    except Exception:
        pass

    # 5. Audit gate: return need_confirm items to user
    if need_confirm_list:
        return {"result": None, "need_confirm_items": need_confirm_list}

    # 6. SQL generation
    if llm_caller is None:
        return {"error": "LLM caller required for SQL generation"}
    try:
        from sql.generator import generate_sql
        sql = await generate_sql(nl_text, matches, norm_values, schema_desc, llm_caller=_llm_call)
    except RuntimeError:  # LLM limit
        return {"error": "LLM call limit reached — cannot generate SQL.", "need_confirm_items": []}
    if sql is None:
        return {"error": "SQL generation failed."}

    # 7. Security validation
    from sql.security import validate_sql
    sec = validate_sql(sql)
    if not sec["passed"]:
        try:
            from sql.generator import generate_sql
            retry_sql = await generate_sql(
                nl_text + f" [安全检查失败: {sec['reason']}]", matches, norm_values,
                schema_desc, llm_caller=_llm_call,
            )
            if retry_sql and validate_sql(retry_sql)["passed"]:
                sql = retry_sql
            else:
                return {"error": f"SQL security check failed: {sec['reason']}"}
        except RuntimeError:
            return {"error": f"SQL security check failed: {sec['reason']} (LLM retry limit)"}

    # 8. Execution
    if query_executor is None:
        return {"sql": sql, "result": "(dry-run: no executor)"}
    try:
        from sql.executor import execute_sql
        exec_result = await execute_sql(session, sql)
    except Exception as e:
        return {"error": f"SQL execution failed: {e}", "sql": sql}

    if "error" in exec_result:
        return {"error": exec_result["error"], "sql": sql}

    # 9. Result summary (aggregate only via LLM)
    result_data = exec_result
    summary_text = None
    if _is_aggregate(sql):
        try:
            system = "Summarize the query result in one natural-language sentence."
            user = f"Query: {nl_text}\nResult: {result_data['rows']}"
            summary_text = await _llm_call(system, user)
        except Exception:
            summary_text = f"Query returned {len(result_data['rows'])} rows."

    return {
        "result": result_data,
        "summary": summary_text or f"Returned {len(result_data['rows'])} row(s).",
        "sql": sql,
        "need_confirm_items": [],
    }


def _is_aggregate(sql: str) -> bool:
    import re
    return bool(re.search(r"(?i)\b(COUNT|SUM|AVG|MIN|MAX)\s*\(", sql))
