"""Tests for DAG executor (#39)."""

import pytest
from pipeline.multi_step import execute_dag, _topological_sort


class TestTopologicalSort:
    def test_linear_dag(self):
        plan = [
            {"id": "a", "dependencies": []},
            {"id": "b", "dependencies": ["a"]},
        ]
        order = _topological_sort(plan)
        assert order == ["a", "b"]

    def test_parallel_dag(self):
        plan = [
            {"id": "a", "dependencies": []},
            {"id": "b", "dependencies": []},
        ]
        order = _topological_sort(plan)
        assert set(order) == {"a", "b"}

    def test_cycle_detected(self):
        plan = [
            {"id": "a", "dependencies": ["b"]},
            {"id": "b", "dependencies": ["a"]},
        ]
        assert _topological_sort(plan) is None


class TestExecuteDag:
    @pytest.mark.asyncio
    async def test_executes_simple_plan(self):
        plan = [{"id": "a", "type": "sql_query", "params": {}, "dependencies": []}]
        r = await execute_dag(plan, "ds")
        assert len(r["results"]) == 1
        assert r["errors"] == []

    @pytest.mark.asyncio
    async def test_detects_cycle(self):
        plan = [
            {"id": "a", "dependencies": ["b"], "type": "sql_query", "params": {}},
            {"id": "b", "dependencies": ["a"], "type": "sql_query", "params": {}},
        ]
        r = await execute_dag(plan, "ds")
        assert "Cyclic" in r.get("error", "")

    @pytest.mark.asyncio
    async def test_empty_plan(self):
        r = await execute_dag([], "ds")
        assert r["results"] == []
