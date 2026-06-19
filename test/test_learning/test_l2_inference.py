"""Tests for L2 LLM semantic inference — structured-signal prompting, parsing, retry."""

import pytest

from learning.l2_inference import (
    FieldSignal,
    build_llm_prompt,
    call_llm_with_retry,
    parse_llm_response,
)


class TestBuildLlmPrompt:
    """Test LLM prompt construction from structured signals only."""

    def test_prompt_contains_table_and_field_signals(self):
        prompt = build_llm_prompt(
            table_name="orders",
            fields=[
                FieldSignal(name="status", data_type="varchar", enum_values=["active", "pending"]),
                FieldSignal(name="amount", data_type="numeric"),
            ],
        )
        assert "orders" in prompt
        assert "status" in prompt
        assert "amount" in prompt
        assert "varchar" in prompt
        # Enum values (de-duplicated low-cardinality candidates) are part of
        # the structured signal and ARE sent.
        assert "active" in prompt

    def test_prompt_includes_comment_and_split_signals(self):
        prompt = build_llm_prompt(
            table_name="users",
            fields=[
                FieldSignal(
                    name="email_addr",
                    data_type="varchar",
                    comment="用户邮箱",
                    split="电子邮件地址",
                )
            ],
        )
        assert "用户邮箱" in prompt
        assert "电子邮件地址" in prompt

    def test_prompt_forbids_using_business_data_rows(self):
        """Governance: prompt must instruct the LLM not to use business data rows."""
        prompt = build_llm_prompt(
            table_name="users",
            fields=[FieldSignal(name="email", data_type="varchar")],
        )
        assert "业务数据" in prompt
        # No sample-data section is emitted.
        assert "样本数据" not in prompt

    def test_prompt_excludes_arbitrary_raw_values(self):
        """No code path injects raw row values; a sentinel must never appear."""
        prompt = build_llm_prompt(
            table_name="users",
            fields=[FieldSignal(name="email", data_type="varchar", enum_values=["a@example.com"])],
        )
        assert "RAW_ROW_SENTINEL_VALUE" not in prompt

    def test_prompt_requests_json_format(self):
        prompt = build_llm_prompt(
            table_name="users",
            fields=[FieldSignal(name="email", data_type="varchar")],
        )
        assert "JSON" in prompt or "json" in prompt
        assert "columns" in prompt

    def test_prompt_handles_empty_fields(self):
        prompt = build_llm_prompt(table_name="empty_table", fields=[])
        assert "empty_table" in prompt


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
        async def mock_caller(system_prompt, user_prompt):
            return '{"columns": {"status": "订单状态"}}'

        result = await call_llm_with_retry(
            mock_caller, "orders", [FieldSignal(name="status", data_type="varchar")]
        )
        assert result == {"status": "订单状态"}

    @pytest.mark.asyncio
    async def test_rate_limit_then_success(self):
        from learning.l2_inference import RateLimitError

        call_count = 0

        async def mock_caller(system_prompt, user_prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitError("429")
            return '{"columns": {"status": "订单状态"}}'

        import learning.l2_inference as l2mod

        original_sleep = l2mod.asyncio.sleep

        async def fake_sleep(seconds):
            pass

        l2mod.asyncio.sleep = fake_sleep
        try:
            result = await call_llm_with_retry(
                mock_caller, "orders", [FieldSignal(name="status", data_type="varchar")]
            )
            assert result == {"status": "订单状态"}
            assert call_count == 2
        finally:
            l2mod.asyncio.sleep = original_sleep

    @pytest.mark.asyncio
    async def test_all_retries_fail_returns_none(self):
        from learning.l2_inference import RateLimitError

        async def mock_caller(system_prompt, user_prompt):
            raise RateLimitError("429")

        import learning.l2_inference as l2mod

        original_sleep = l2mod.asyncio.sleep

        async def fake_sleep(seconds):
            pass

        l2mod.asyncio.sleep = fake_sleep
        try:
            result = await call_llm_with_retry(
                mock_caller, "orders", [FieldSignal(name="status", data_type="varchar")]
            )
            assert result is None
        finally:
            l2mod.asyncio.sleep = original_sleep

    @pytest.mark.asyncio
    async def test_non_rate_limit_error_returns_none(self):
        async def mock_caller(system_prompt, user_prompt):
            raise ConnectionError("network error")

        result = await call_llm_with_retry(
            mock_caller, "orders", [FieldSignal(name="status", data_type="varchar")]
        )
        assert result is None
