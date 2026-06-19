"""Tests for NormalizedValue + time parser (issue #23)."""

import pytest
from datetime import date

from normalizer.time_parser import FIXED_DATE_PERIODS, parse_time
from normalizer.types import NormalizedValue


class TestNormalizedValue:
    def test_defaults(self):
        nv = NormalizedValue(original="x")
        assert nv.confidence == 0.0
        assert not nv.need_confirm
        assert nv.alternatives == []

    def test_need_confirm_flags(self):
        nv = NormalizedValue(original="x", need_confirm=True)
        assert nv.need_confirm
        assert nv.db_representation is None


class TestTimeParser:
    def test_today(self):
        v = parse_time("今天")
        assert v.matched_by == "relative_time"
        assert not v.need_confirm
        assert "date >=" in v.db_representation

    def test_yesterday(self):
        v = parse_time("昨天")
        assert v.matched_by == "relative_time"
        assert not v.need_confirm

    def test_this_week(self):
        v = parse_time("本周")
        assert v.matched_by == "relative_time"
        assert not v.need_confirm
        assert isinstance(v.normalized, tuple)

    def test_last_week(self):
        v = parse_time("上周")
        assert v.matched_by == "relative_time"
        assert not v.need_confirm

    def test_this_month(self):
        v = parse_time("本月")
        assert v.matched_by == "relative_time"
        assert not v.need_confirm

    def test_last_month(self):
        v = parse_time("上月")
        assert v.matched_by == "relative_time"
        assert not v.need_confirm

    def test_this_quarter(self):
        v = parse_time("本季度")
        assert v.matched_by == "relative_time"
        assert not v.need_confirm

    def test_this_year(self):
        v = parse_time("今年")
        assert v.matched_by == "relative_time"
        assert not v.need_confirm
        assert v.normalized[0] == date(date.today().year, 1, 1)

    def test_absolute_iso_date(self):
        v = parse_time("2026-05-01")
        assert v.matched_by == "absolute_time"
        assert "date = '2026-05-01'" in v.db_representation

    def test_absolute_cn_date(self):
        v = parse_time("2026年5月1日")
        assert v.matched_by == "absolute_time"

    def test_absolute_year_month(self):
        v = parse_time("2026年5月")
        assert v.matched_by == "absolute_time"
        assert "date >=" in v.db_representation and "date <=" in v.db_representation

    def test_fixed_period_618(self):
        v = parse_time("618")
        assert v.matched_by == "fixed_period"
        assert "06-01" in v.db_representation and "06-18" in v.db_representation

    def test_fixed_period_exists(self):
        assert "双十一" in FIXED_DATE_PERIODS
        assert "618" in FIXED_DATE_PERIODS

    def test_unparseable_returns_need_confirm(self):
        v = parse_time("未定义时间词")
        assert v.need_confirm
        assert v.db_representation is None

    def test_empty_string_returns_need_confirm(self):
        v = parse_time("")
        assert v.need_confirm
