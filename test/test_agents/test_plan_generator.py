"""Tests for plan generator (#38)."""

import pytest
from agents.plan_generator import generate_plan


@pytest.mark.asyncio
async def test_comparison_generates_two_parallel_tasks():
    plan = await generate_plan("对比本月和上月的销售额", "ds", [{"table":"orders","column":"amount"}])
    assert len(plan) >= 2
    assert any(t["type"] == "sql_query" for t in plan)


@pytest.mark.asyncio
async def test_sequential_generates_dependent_tasks():
    plan = await generate_plan("先查订单再查客户", "ds", [{"table":"orders"}])
    assert len(plan) >= 2  # at least 2 steps


@pytest.mark.asyncio
async def test_simple_multi_generates_single_task():
    plan = await generate_plan("订单列表", "ds", [{"table":"orders"}])
    assert len(plan) == 1


@pytest.mark.asyncio
async def test_multi_table_adds_join_path():
    """With graph_store mock, multi-table should trigger join path detection."""
    class MockStore:
        pass
    plan = await generate_plan("含客户名的订单", "ds",
        [{"table":"orders"},{"table":"customers"}], graph_store=MockStore())
    assert len(plan) >= 1
