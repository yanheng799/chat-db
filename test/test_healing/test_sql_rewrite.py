"""Tests for SQL rewrite healing (#42)."""

import pytest
from healing.sql_rewrite import heal_sql


def _mock_llm(response):
    async def caller(system, user):
        return response
    return caller


@pytest.mark.asyncio
async def test_heal_returns_valid_sql():
    llm = _mock_llm("SELECT id, name FROM orders LIMIT 10")
    result = await heal_sql("SELEC id FROM orders", "syntax error", "sql_syntax_error", llm_caller=llm)
    assert result and "SELECT" in result


@pytest.mark.asyncio
async def test_heal_returns_none_when_validation_fails():
    llm = _mock_llm("DROP TABLE orders")  # will fail security check
    result = await heal_sql("bad sql", "error", "sql_syntax_error", llm_caller=llm)
    assert result is None


@pytest.mark.asyncio
async def test_heal_returns_none_when_llm_errors():
    async def boom(system, user):
        raise RuntimeError("LLM down")
    result = await heal_sql("bad sql", "error", "sql_syntax_error", llm_caller=boom)
    assert result is None
