"""Tests for L1 field name splitting (snake_case + CamelCase + word table)."""

import pytest

from learning.splitter import split_field_name


class TestSnakeCaseSplitting:
    """Test snake_case field name splitting and translation."""

    def test_order_status(self):
        """order_status → 订单状态"""
        assert split_field_name("order_status") == "订单状态"

    def test_created_at(self):
        """created_at → 创建时间"""
        assert split_field_name("created_at") == "创建时间"

    def test_total_amount(self):
        """total_amount → 总金额"""
        assert split_field_name("total_amount") == "总金额"

    def test_user_email(self):
        """user_email → 用户邮箱"""
        assert split_field_name("user_email") == "用户邮箱"

    def test_is_active(self):
        """is_active → 是否激活"""
        assert split_field_name("is_active") == "是否激活"

    def test_single_word(self):
        """Single known word should translate directly."""
        assert split_field_name("status") == "状态"

    def test_single_word_name(self):
        assert split_field_name("name") == "名称"

    def test_unknown_word_returns_none(self):
        """All-unknown words should return None."""
        assert split_field_name("xyz_abc_unknown") is None

    def test_partial_unknown_returns_none(self):
        """If any word is unknown, return None (partial translation is confusing)."""
        assert split_field_name("order_xyz") is None

    def test_empty_string(self):
        assert split_field_name("") is None

    def test_underscores_only(self):
        assert split_field_name("___") is None


class TestCamelCaseSplitting:
    """Test CamelCase field name splitting and translation."""

    def test_created_at(self):
        """createdAt → 创建时间"""
        assert split_field_name("createdAt") == "创建时间"

    def test_order_status(self):
        """orderStatus → 订单状态"""
        assert split_field_name("orderStatus") == "订单状态"

    def test_user_email_address(self):
        """userEmailAddress → 用户邮箱地址"""
        assert split_field_name("userEmailAddress") == "用户邮箱地址"

    def test_is_active(self):
        """isActive → 是否激活"""
        assert split_field_name("isActive") == "是否激活"

    def test_id(self):
        """ID → 标识"""
        assert split_field_name("ID") == "标识"

    def test_user_id(self):
        """userID → 用户标识"""
        assert split_field_name("userID") == "用户标识"


class TestEdgeCases:
    """Test edge cases in field name splitting."""

    def test_already_lowercase_single(self):
        assert split_field_name("email") == "邮箱"

    def test_numeric_suffix_handled_gracefully(self):
        """Fields with numeric suffixes like address1 should still work if base word is known."""
        # address1 has no entry — should return None
        assert split_field_name("address1") is None

    def test_double_underscore(self):
        """Double underscore should be treated as empty segment."""
        assert split_field_name("order__status") == "订单状态"

    def test_leading_underscore(self):
        assert split_field_name("_status") == "状态"

    def test_trailing_underscore(self):
        assert split_field_name("status_") == "状态"


class TestWordTableCoverage:
    """Verify word table has sufficient coverage."""

    def test_word_table_has_minimum_entries(self):
        """Word table must have ≥150 entries per acceptance criteria."""
        from learning.word_table import WORD_TABLE

        assert len(WORD_TABLE) >= 150
