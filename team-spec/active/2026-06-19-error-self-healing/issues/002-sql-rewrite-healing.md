# 实现 SQL 重写修复——LLM 多策略修复+语法校验+重试

## Parent

PRD：`team-spec/active/2026-06-19-error-self-healing/prd/prd.md`（7.4 SQL 重写）

## What to build

实现 SQL 语法错误与类型不匹配的自动修复：当分类为 `sql_syntax_error` 或 `type_mismatch` 时，将错误信息（错误消息 + 原 SQL）作为上下文发给 LLM 做多策略修复（语法修正 / CAST 转换 / 引号修复），修复后的 SQL 经 Phase 5 安全校验通过后重试执行。每条错误类型只尝试一次对应策略；最多 3 次总重试（含元数据同步策略），超限 → 降级告知用户。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given SQL 语法错误，When LLM 重写，Then 生成语法正确的 SQL → 安全校验通过 → 重试执行。
- [ ] Given 类型不匹配错误（如 `integer = 'text'`），When LLM 修复，Then 添加 CAST 或类型转换函数。
- [ ] Given LLM 重写后的 SQL 安全校验失败，When 重试，Then 不执行、进入下一次重试或返回失败。
- [ ] 同一查询每种策略只尝试一次；最多 3 次总重试，超限 → 告知用户 + 记录 `healing_records`。

## Blocked by

- None

## Notes

- LLM 复用 `llm/client.py`（create_llm_caller）。LLM 调用计入 `pipeline_llm_max_calls`。
- 安全校验复用 Phase 5 `validate_sql`。
- 与 #1（分类器+元数据同步）的去重逻辑：自愈 Agent 维护一个已尝试策略集合，避免重复。

## Publish Status

- Status: created
- Updated At: 2026-06-19T07:49:56Z
- GitHub Number: 42
- GitHub URL: https://github.com/yanheng799/chat-db/issues/42
