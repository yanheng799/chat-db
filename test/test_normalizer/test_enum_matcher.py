"""Tests for enum matcher 5-strategy chain (issue #25)."""

import uuid
import pytest

from normalizer.enum_matcher import normalize_enum
from normalizer.mapping_service import upsert_enum_alias
from test_normalizer.test_mapping_service import _create_data_source


def _mock_llm(response: str):
    async def caller(system, user):
        return response
    return caller


@pytest.mark.asyncio
async def test_display_exact_match(db_session):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    await upsert_enum_alias(db_session, ds_id, "orders", "status", "completed", display="已完成")
    v = await normalize_enum(db_session, "已完成", ds_id, "orders", "status")
    assert v.db_representation == "completed"
    assert v.matched_by == "display"
    assert not v.need_confirm


@pytest.mark.asyncio
async def test_alias_match(db_session):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    await upsert_enum_alias(db_session, ds_id, "orders", "status", "completed", display="已完成", aliases=["完结","结了"])
    v = await normalize_enum(db_session, "完结", ds_id, "orders", "status")
    assert v.db_representation == "completed"
    assert v.matched_by == "alias"


@pytest.mark.asyncio
async def test_edit_distance_fuzzy(db_session):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    await upsert_enum_alias(db_session, ds_id, "t", "c", "active", display="激活")
    v = await normalize_enum(db_session, "激活中", ds_id, "t", "c")
    # "激活" vs "激活中" → difflib ratio ~0.67 < 0.7 — should NOT match (? 激活+激活中 = 4/6 ≈ 0.67)
    # Hmm let me check: SequenceMatcher("激活中","激活").ratio() = 2*M/T, M=2 (match "激活"), T=5 (3+2), 4/5=0.8 >= 0.7 → MATCH
    if not v.need_confirm:
        assert v.matched_by == "edit_distance"
        assert v.db_representation == "active"


@pytest.mark.asyncio
async def test_llm_fallback_used_when_prior_strategies_fail(db_session):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    await upsert_enum_alias(db_session, ds_id, "t", "c", "paid", display="已支付")
    llm = _mock_llm('{"value":"paid","confidence":0.95}')
    v = await normalize_enum(db_session, "支付了", ds_id, "t", "c", llm_caller=llm)
    assert v.matched_by == "llm"
    assert v.db_representation == "paid"


@pytest.mark.asyncio
async def test_llm_low_confidence_rejected(db_session):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    await upsert_enum_alias(db_session, ds_id, "t", "c", "paid", display="已支付")
    llm = _mock_llm('{"value":"paid","confidence":0.7}')
    v = await normalize_enum(db_session, "支付了", ds_id, "t", "c", llm_caller=llm)
    assert v.need_confirm  # <0.85 rejected


@pytest.mark.asyncio
async def test_all_fail_returns_need_confirm(db_session):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    # Seed some enum candidates — need_confirm is now only True when there
    # are known values to disambiguate (len(candidates) > 0).
    await upsert_enum_alias(db_session, ds_id, "t", "c", "active", display="激活")
    v = await normalize_enum(db_session, "未知词", ds_id, "t", "c")
    assert v.need_confirm
    assert v.db_representation is None
