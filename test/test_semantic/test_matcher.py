"""Tests for 4-layer semantic matcher (#31)."""

import pytest
from semantic.matcher import match_semantic


def _mock_llm(response):
    async def caller(system, user):
        return response
    return caller


@pytest.mark.asyncio
async def test_hot_word_match():
    m = await match_semantic("销售额", "ds")
    assert len(m) == 1
    assert m[0]["matched_by"] == "hot_word"
    assert m[0]["locked"] is True


@pytest.mark.asyncio
async def test_hot_word_within_sentence():
    m = await match_semantic("查一下昨天的销售额", "ds")
    assert len(m) >= 1
    assert any(r["matched_by"] == "hot_word" for r in m)


@pytest.mark.asyncio
async def test_industry_term_translation():
    # "GMV" → "销售额" → hot-word
    m = await match_semantic("GMV是多少", "ds")
    assert any(r["matched_by"] == "hot_word" for r in m)


@pytest.mark.asyncio
async def test_vector_search_fallback():
    async def vs(query, ds):
        return [{"table":"orders","column":"status","score":0.85}]
    m = await match_semantic("订单状态", "ds", vector_search=vs)
    assert m[0]["matched_by"] == "vector"


@pytest.mark.asyncio
async def test_llm_fallback():
    async def vs(query, ds):
        return []
    llm = _mock_llm('[{"table":"orders","column":"status","confidence":0.9}]')
    m = await match_semantic("订单当前的状态", "ds", vector_search=vs, llm_caller=llm)
    assert m[0]["matched_by"] == "llm_fallback"
    assert m[0]["need_confirm"] is True


@pytest.mark.asyncio
async def test_all_layers_fail_empty():
    m = await match_semantic("完全未知的查询xys", "ds")
    assert m == []
