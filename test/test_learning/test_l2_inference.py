"""Tests for L2 LLM semantic inference — sampling, prompting, parsing, retry."""

import pytest

from learning.l2_inference import (
    build_llm_prompt,
    build_sample_query,
    parse_llm_response,
    truncate_value,
)


class TestTruncateValue:
    """Test TEXT value truncation at 200 chars."""

    def test_short_value_unchanged(self):
        assert truncate_value("hello") == "hello"

    def test_exactly_200_chars(self):
        val = "x" * 200
        assert truncate_value(val) == val

    def test_over_200_truncated(self):
        val = "x" * 250
        assert truncate_value(val) == "x" * 200
        assert len(truncate_value(val)) == 200

    def test_none_returns_none(self):
        assert truncate_value(None) is None

    def test_numeric_returns_as_is(self):
        assert truncate_value(42) == 42


class TestBuildSampleQuery:
    """Test sample query builder — excludes BLOB types, limits 5 rows."""

    def test_basic_query_pg(self):
        columns = [
            _make_col("name", "varchar"),
            _make_col("bio", "text"),
            _make_col("avatar", "blob"),
            _make_col("data", "binary"),
        ]
        sql = build_sample_query("users", "public", columns, "postgresql")
        assert "LIMIT 5" in sql
        # BLOB/BINARY columns excluded
        assert '"name"' in sql
        assert '"bio"' in sql
        assert '"avatar"' not in sql
        assert '"data"' not in sql

    def test_basic_query_mysql(self):
        columns = [
            _make_col("name", "varchar"),
            _make_col("photo", "varbinary"),
        ]
        sql = build_sample_query("users", None, columns, "mysql")
        assert "LIMIT 5" in sql
        assert "`name`" in sql
        assert "`photo`" not in sql

    def test_all_excluded_returns_none(self):
        columns = [
            _make_col("blob1", "blob"),
            _make_col("blob2", "binary"),
        ]
        result = build_sample_query("users", "public", columns, "postgresql")
        assert result is None

    def test_empty_columns_returns_none(self):
        result = build_sample_query("users", "public", [], "postgresql")
        assert result is None


class TestBuildLlmPrompt:
    """Test LLM prompt construction."""

    def test_prompt_contains_table_and_fields(self):
        prompt = build_llm_prompt(
            table_name="orders",
            field_names=["status", "amount"],
            sample_rows=[
                {"status": "active", "amount": 100},
                {"status": "pending", "amount": 200},
            ],
        )
        assert "orders" in prompt
        assert "status" in prompt
        assert "amount" in prompt
        assert "active" in prompt

    def test_prompt_requests_json_format(self):
        prompt = build_llm_prompt(
            table_name="users",
            field_names=["email"],
            sample_rows=[{"email": "a@b.com"}],
        )
        assert "JSON" in prompt or "json" in prompt
        assert "columns" in prompt

    def test_prompt_forbids_data_memorization(self):
        prompt = build_llm_prompt(
            table_name="users",
            field_names=["email"],
            sample_rows=[{"email": "a@b.com"}],
        )
        # Should instruct LLM not to memorize/output specific values
        assert "不" in prompt or "not" in prompt.lower() or "不要" in prompt

    def test_prompt_handles_no_sample_rows(self):
        prompt = build_llm_prompt(
            table_name="empty_table",
            field_names=["col1"],
            sample_rows=[],
        )
        assert "empty_table" in prompt
        assert "col1" in prompt


class TestParseLlmResponse:
    """Test LLM JSON response parsing."""

    def test_valid_json_response(self):
        response = '{"columns": {"status": "订单状态", "amount": "订单金额"}}'
        result = parse_llm_response(response)
        assert result == {"status": "订单状态", "amount": "订单金额"}

    def test_json_with_markdown_fences(self):
        response = '```json\n{"columns": {"status": "订单状态"}}\n```'
        result = parse_llm_response(response)
        assert result == {"status": "订单状态"}

    def test_json_without_columns_key(self):
        response = '{"status": "订单状态"}'
        result = parse_llm_response(response)
        assert result == {"status": "订单状态"}

    def test_malformed_json_returns_empty(self):
        result = parse_llm_response("this is not json")
        assert result == {}

    def test_empty_response_returns_empty(self):
        result = parse_llm_response("")
        assert result == {}

    def test_non_dict_columns_returns_empty(self):
        result = parse_llm_response('{"columns": [1, 2, 3]}')
        assert result == {}


class TestCallLlmWithRetry:
    """Test LLM call with retry logic."""

    @pytest.mark.asyncio
    async def test_successful_call(self):
        from learning.l2_inference import call_llm_with_retry

        async def mock_caller(system_prompt, user_prompt):
            return '{"columns": {"status": "订单状态"}}'

        result = await call_llm_with_retry(
            mock_caller, "orders", ["status"], [{"status": "active"}]
        )
        assert result == {"status": "订单状态"}

    @pytest.mark.asyncio
    async def test_rate_limit_then_success(self):
        from learning.l2_inference import RateLimitError, call_llm_with_retry

        call_count = 0

        async def mock_caller(system_prompt, user_prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitError("429")
            return '{"columns": {"status": "订单状态"}}'

        # Patch sleep to speed up test
        import learning.l2_inference as l2mod

        original_sleep = l2mod.asyncio.sleep

        async def fake_sleep(seconds):
            pass

        l2mod.asyncio.sleep = fake_sleep
        try:
            result = await call_llm_with_retry(
                mock_caller, "orders", ["status"], []
            )
            assert result == {"status": "订单状态"}
            assert call_count == 2
        finally:
            l2mod.asyncio.sleep = original_sleep

    @pytest.mark.asyncio
    async def test_all_retries_fail_returns_none(self):
        from learning.l2_inference import RateLimitError, call_llm_with_retry

        async def mock_caller(system_prompt, user_prompt):
            raise RateLimitError("429")

        import learning.l2_inference as l2mod

        original_sleep = l2mod.asyncio.sleep

        async def fake_sleep(seconds):
            pass

        l2mod.asyncio.sleep = fake_sleep
        try:
            result = await call_llm_with_retry(
                mock_caller, "orders", ["status"], []
            )
            assert result is None
        finally:
            l2mod.asyncio.sleep = original_sleep

    @pytest.mark.asyncio
    async def test_non_rate_limit_error_returns_none(self):
        from learning.l2_inference import call_llm_with_retry

        async def mock_caller(system_prompt, user_prompt):
            raise ConnectionError("network error")

        result = await call_llm_with_retry(
            mock_caller, "orders", ["status"], []
        )
        assert result is None


# --- Helpers ---

def _make_col(name: str, data_type: str):
    from dataclasses import dataclass

    @dataclass
    class FakeCol:
        column_name: str
        data_type: str

    return FakeCol(column_name=name, data_type=data_type)
