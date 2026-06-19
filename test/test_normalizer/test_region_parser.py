"""Tests for region parser (issue #26)."""

import uuid
import pytest

from normalizer.region_parser import normalize_region
from normalizer.mapping_service import upsert_region
from test_normalizer.test_mapping_service import _create_data_source


@pytest.mark.asyncio
async def test_exact_city_match(db_session):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    await upsert_region(db_session, ds_id, code="310000", parent_code=None, level="city", name="上海")
    v = await normalize_region(db_session, "上海", ds_id)
    assert not v.need_confirm
    assert "上海" in v.db_representation


@pytest.mark.asyncio
async def test_alias_match(db_session):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    await upsert_region(db_session, ds_id, code="310000", parent_code=None, level="city", name="上海", aliases=["魔都"])
    v = await normalize_region(db_session, "魔都", ds_id)
    assert not v.need_confirm


@pytest.mark.asyncio
async def test_unknown_city_need_confirm(db_session):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    v = await normalize_region(db_session, "火星", ds_id)
    assert v.need_confirm


@pytest.mark.asyncio
async def test_custom_area_expands_to_children(db_session):
    ds_id = uuid.uuid4()
    await _create_data_source(db_session, ds_id)
    await upsert_region(db_session, ds_id, code="EAST", parent_code=None, level="custom", name="华东")
    await upsert_region(db_session, ds_id, code="310000", parent_code="EAST", level="city", name="上海")
    await upsert_region(db_session, ds_id, code="320100", parent_code="EAST", level="city", name="南京")
    v = await normalize_region(db_session, "华东", ds_id)
    assert not v.need_confirm
    assert "上海" in v.db_representation and "南京" in v.db_representation
    assert "IN (" in v.db_representation
