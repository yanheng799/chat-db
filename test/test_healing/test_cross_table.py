"""Tests for cross-table healing (#43)."""

import pytest
from healing.cross_table import heal_cross_table


@pytest.mark.asyncio
async def test_finds_candidate_via_vector_and_graph():
    async def vs(query, ds):
        return [{"table": "customers", "column": "name", "score": 0.85}]

    class MockGraph:
        pass

    async def mock_shortest(graph, ds, a, b):
        return [{"from_table": "orders", "from_column": "customer_id", "to_table": "customers", "to_column": "id"}]

    with pytest.MonkeyPatch.context() as mp:
        import knowledge.graph_query as gq
        mp.setattr(gq, "shortest_join_path", mock_shortest)
        result = await heal_cross_table("name", "orders", "ds", vector_search=vs, graph_store=MockGraph())
        assert result is not None
        assert result["candidate_table"] == "customers"


@pytest.mark.asyncio
async def test_no_candidate_above_threshold():
    async def vs(query, ds):
        return [{"table": "customers", "score": 0.5}]  # below 0.7

    result = await heal_cross_table("name", "orders", "ds", vector_search=vs)
    assert result is None


@pytest.mark.asyncio
async def test_vector_search_failure_returns_none():
    async def vs(query, ds):
        raise RuntimeError("down")

    result = await heal_cross_table("name", "orders", "ds", vector_search=vs)
    assert result is None
