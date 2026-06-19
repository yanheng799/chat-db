"""Tests for name abbreviation matcher (issue #27)."""

import uuid
import pytest

from normalizer.name_matcher import normalize_name
from normalizer.mapping_service import upsert_name_mapping
from test_normalizer.test_mapping_service import _create_data_source


@pytest.mark.asyncio
async def test_exact_short_name_match(db_session):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    await upsert_name_mapping(db_session, ds_id, short_name="华为", full_name="Huawei Technologies")
    v = await normalize_name(db_session, "华为", ds_id)
    assert v.db_representation == "Huawei Technologies"
    assert v.matched_by == "exact"


@pytest.mark.asyncio
async def test_alias_match(db_session):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    await upsert_name_mapping(db_session, ds_id, short_name="HW", full_name="Huawei Technologies", aliases=["华为"])
    v = await normalize_name(db_session, "华为", ds_id)
    assert v.matched_by == "alias"
    assert v.db_representation == "Huawei Technologies"


@pytest.mark.asyncio
async def test_keyword_partial_match(db_session):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    await upsert_name_mapping(db_session, ds_id, short_name="huawei", full_name="Huawei Technologies")
    v = await normalize_name(db_session, "huawei", ds_id)
    assert v.matched_by in ("exact", "keyword")


@pytest.mark.asyncio
async def test_name_not_found_need_confirm(db_session):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    v = await normalize_name(db_session, "不存在的名字", ds_id)
    assert v.need_confirm


@pytest.mark.asyncio
async def test_like_fallback(db_session):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)

    async def mock_exec(sql):
        return ["Huawei Tech", "HW Inc"]

    v = await normalize_name(db_session, "未知简称", ds_id, query_executor=mock_exec)
    assert v.matched_by == "like_fallback"
    assert len(v.alternatives) == 2
