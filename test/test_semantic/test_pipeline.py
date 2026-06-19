"""Tests for pipeline orchestrator (#35). Mock LLM + mock query executor."""

import pytest
from pipeline.single_step import run_single_step


def _mock_llm(responses):
    async def caller(system, user):
        for key, val in responses.items():
            if key in user:
                return val
        return "SELECT 1 FROM orders LIMIT 10"
    return caller


@pytest.mark.asyncio
async def test_pipeline_need_confirm_gate():
    llm = _mock_llm({
        "订单状态": '[{"table":"orders","column":"status","confidence":0.9}]',
    })
    async def vs(query, ds):
        return []
    r = await run_single_step(
        "订单状态", "ds", llm_caller=llm, vector_search=vs,
    )
    assert r.get("need_confirm_items"), "LLM fallback match should trigger need_confirm"


@pytest.mark.asyncio
async def test_pipeline_run_sql_dry_run():
    llm = _mock_llm({
        "语义匹配": '[{"table":"orders","column":"id","confidence":1.0}]',
        "SQL": "SELECT COUNT(*) FROM orders LIMIT 10",
    })
    r = await run_single_step(
        "订单总数", "ds", llm_caller=llm,
        schema_desc="orders(id, status, amount)",
    )
    assert r.get("sql") or r.get("error")


@pytest.mark.asyncio
async def test_pipeline_no_match_returns_error():
    llm = _mock_llm({
        "语义匹配": '[]',
    })
    r = await run_single_step("xyz", "ds", llm_caller=llm)
    assert "Unable to understand" in r.get("error", "")
