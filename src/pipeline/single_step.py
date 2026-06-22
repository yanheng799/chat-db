"""Single-step query pipeline orchestrator (Phase 5 / issue #35).

Ties together time parsing → semantic matching → value normalization →
SQL generation → security validation → audit → execution → result summary.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)
_log = logging.getLogger("uvicorn.error")

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
    on_progress: Any = None,
    context: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Run a full single-step query pipeline. Returns {result, need_confirm_items, error}.

    ``on_progress`` is an optional ``async (phase, message) -> None`` callback
    invoked at each pipeline phase (``semantic`` / ``sql`` / ``security`` /
    ``execute``); the SSE gateway uses it to stream progress to the client.

    ``context`` is an optional list of ``{role, content}`` dicts representing
    previous conversation turns.  When provided, it is prepended to every LLM
    user prompt so the model can resolve anaphora (e.g. "其中最大的文件").
    """
    llm_calls = 0
    need_confirm_list: list[dict] = []

    # Build a context prefix once and inject into all LLM user prompts
    _ctx_prefix = ""
    if context:
        lines = ["以下是之前的对话记录，仅用于参考上下文："]
        for turn in context[-5:]:  # keep last 5 turns
            role = "用户" if turn.get("role") == "user" else "助手"
            text = (turn.get("content") or "")[:200]
            lines.append(f"{role}：{text}")
        _ctx_prefix = "\n".join(lines) + "\n---\n"
    logger.info("[ctx] run_single_step received context=%d turns, prefix_len=%d, prefix_preview=%r",
                len(context or []), len(_ctx_prefix), _ctx_prefix[:160])
    _log.info("[ctx] run_single_step received context=%d turns, prefix_len=%d, prefix_preview=%r",
              len(context or []), len(_ctx_prefix), _ctx_prefix[:160])

    async def _emit(phase: str, message: str) -> None:
        if on_progress is not None:
            try:
                await on_progress(phase, message)
            except Exception as e:  # noqa: BLE001 - progress must never break the pipeline
                logger.warning("on_progress(%s) failed: %s", phase, e)

    def _llm_call(system, user):
        nonlocal llm_calls
        if llm_calls >= max_llm_calls:
            raise RuntimeError(f"LLM call limit ({max_llm_calls}) reached")
        llm_calls += 1
        user_with_ctx = _ctx_prefix + user if _ctx_prefix else user
        logger.info("[ctx] _llm_call#%d ctx_injected=%s user_prompt_head=%r",
                    llm_calls, bool(_ctx_prefix), user_with_ctx[:200])
        _log.info("[ctx] _llm_call#%d ctx_injected=%s user_prompt_head=%r",
                  llm_calls, bool(_ctx_prefix), user_with_ctx[:200])
        return llm_caller(system, user_with_ctx)

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

    await _emit("semantic", "语义匹配完成")

    # 3. Post-normalization (enum/region/name for each matched field)
    if session is not None:
        await _emit("normalize", "值标准化中…")
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

    # 5. Try SQL generation (even if confirmation needed — show proposed SQL)
    sql = None
    if llm_caller is not None:
        await _emit("generate", "SQL 生成中…")
        try:
            # Query graph for JOIN paths between matched tables.
            # Use connected_subgraph for a single recursive traversal;
            # fall back to the N×N pairwise shortest_join_path loop if
            # connected_subgraph fails or times out.
            join_paths = None
            if len({m.get("table", "") for m in matches if m.get("table")}) > 1:
                try:
                    from knowledge.graph_query import connected_subgraph, shortest_join_path
                    from knowledge.graph_store import GraphStore
                    tables = list({m["table"] for m in matches if m.get("table")})
                    graph = GraphStore()
                    paths_list: list[dict] = []
                    try:
                        result = await connected_subgraph(
                            graph, data_source_id, tables, min_confidence=0.5,
                        )
                        if result.get("connected"):
                            # Flatten: merge all paths into a single deduped list
                            seen: set[tuple[str, str, str, str]] = set()
                            for path in result["connected"]:
                                for step in path:
                                    key = (step["from_table"], step["from_column"],
                                           step["to_table"], step["to_column"])
                                    if key not in seen:
                                        seen.add(key)
                                        paths_list.append(step)
                            if paths_list:
                                join_paths = paths_list
                        if result.get("unconnected"):
                            logger.warning(
                                "connected_subgraph: %d tables not connected: %s",
                                len(result["unconnected"]), result["unconnected"],
                            )
                    except Exception:
                        logger.warning("connected_subgraph failed, falling back to pairwise shortest_join_path")
                        # Fallback: pairwise shortest_join_path (preserved)
                        paths_list = []
                        for i in range(len(tables)):
                            for j in range(i + 1, len(tables)):
                                path = await shortest_join_path(
                                    graph, data_source_id, tables[i], tables[j],
                                    min_confidence=0.5,
                                )
                                if path:
                                    for step in path:
                                        if step not in paths_list:
                                            paths_list.append(step)
                        if paths_list:
                            join_paths = paths_list
                    finally:
                        graph.close()
                except Exception:
                    pass

            from sql.generator import generate_sql
            sql = await generate_sql(nl_text, matches, norm_values, schema_desc,
                                     llm_caller=_llm_call, join_paths=join_paths)
        except RuntimeError:
            sql = None
        except Exception:
            sql = None

        if sql:
            await _emit("sql", "SQL 已生成")
            try:
                from sql.security import validate_sql
                sec = validate_sql(sql)
                if not sec["passed"]:
                    retry_sql = None
                    try:
                        retry_sql = await generate_sql(
                            nl_text + f" [安全检查失败: {sec['reason']}]", matches, norm_values,
                            schema_desc, llm_caller=_llm_call, join_paths=join_paths,
                        )
                    except Exception:
                        pass
                    if retry_sql:
                        try:
                            if validate_sql(retry_sql)["passed"]:
                                sql = retry_sql
                            else:
                                return {"error": f"SQL security check failed: {sec['reason']}", "sql": sql}
                        except Exception:
                            return {"error": f"SQL security check failed: {sec['reason']}", "sql": sql}
                    else:
                        return {"error": f"SQL security check failed: {sec['reason']}", "sql": sql}
            except Exception:
                pass
            await _emit("security", "安全校验通过")

    # 5b. Audit gate: only block execution if we CANNOT generate SQL
    # If SQL is ready and passes security, continue — show confirm items as warnings
    if need_confirm_list and not sql:
        return {"result": None, "sql": None, "need_confirm_items": need_confirm_list}

    # 6. Fallback: no SQL generated
    if not sql:
        return {"error": "SQL generation failed."}
    if llm_caller is None:
        return {"error": "LLM caller required for SQL generation"}

    # 7. Execution
    if query_executor is not None:
        # Use target datasource connection
        exec_result = await query_executor(sql)
    elif session is not None:
        # Fallback: use app DB session (for backward compat)
        try:
            from sql.executor import execute_sql
            exec_result = await execute_sql(session, sql)
        except Exception as e:
            return {"error": f"SQL execution failed: {e}", "sql": sql}
    else:
        return {"sql": sql, "result": "(dry-run: no executor)"}

    if "error" in exec_result:
        return {"error": exec_result["error"], "sql": sql}

    await _emit("execute", "执行完成")

    # 9. Result summary — LLM for small result sets, generic count for large ones
    result_data = exec_result
    summary_text = None
    row_count = len(result_data["rows"]) if isinstance(result_data, dict) and "rows" in result_data else 0
    if 0 < row_count <= 50:
        try:
            system = (
                "你是一个数据库查询助手。根据用户的问题和查询结果，用一句自然语言中文回答用户的问题。"
                "如果结果是聚合值，直接报告数值。如果结果是列表，简要概括内容（如涉及哪些主要项）。"
                "不要重复列名，不要输出表格。"
            )
            user = f"用户问题：{nl_text}\n查询结果（前50行）：{result_data['rows'][:50]}"
            summary_text = await _llm_call(system, user)
        except Exception:
            summary_text = f"查询返回 {row_count} 条记录。"

    return {
        "result": result_data,
        "summary": summary_text or f"查询返回 {row_count} 条记录。",
        "sql": sql,
        "need_confirm_items": need_confirm_list,
    }
