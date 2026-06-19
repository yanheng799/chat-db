"""Tests for SQL generator (#32)."""

import pytest
from sql.generator import generate_sql


@pytest.mark.asyncio
async def test_generates_select_with_conditions():
    async def mock_llm(system, user):
        return "SELECT COUNT(*) FROM orders WHERE status='completed' LIMIT 100"
    sql = await generate_sql(
        "已完成订单", [{"table":"orders","column":"status"}],
        [{"db_representation":"status='completed'"}],
        "orders(id, status, amount)", llm_caller=mock_llm,
    )
    assert sql and "SELECT" in sql and "LIMIT" in sql


@pytest.mark.asyncio
async def test_strips_markdown_fences():
    async def mock_llm(system, user):
        return "```sql\nSELECT id FROM orders LIMIT 10\n```"
    sql = await generate_sql("orders", [], [], "orders(id)", llm_caller=mock_llm)
    assert sql == "SELECT id FROM orders LIMIT 10"


@pytest.mark.asyncio
async def test_llm_error_returns_none():
    async def boom(system, user):
        raise RuntimeError("LLM down")
    sql = await generate_sql("x", [], [], "t(c)", llm_caller=boom)
    assert sql is None
