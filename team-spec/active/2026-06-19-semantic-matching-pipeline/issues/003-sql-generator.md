# 基于语义匹配结果与标准化值生成只读单步 SQL

## Parent

PRD：`team-spec/active/2026-06-19-semantic-matching-pipeline/prd/prd.md`（5.2 SQL 生成，issue C）

## What to build

实现 SQL 生成器：以语义匹配结果（`{table, column, matched_by}`）+ Phase 4 标准化值 `NormalizedValue.db_representation` + 用户原句为输入，通过 LLM prompt 生成**单表只读 SQL**（约束：只读、`LIMIT ≤ 1000`、禁止 `SELECT *`）。Prompt 注入 schema 上下文（表.列名+类型+语义描述）。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given 语义匹配结果 `{orders.status="completed"}` + 标准化值 `{date BETWEEN '2026-05-01' AND '2026-05-31'}`，When 生成 SQL，Then 生成的 SQL 含正确的 WHERE 子句（`status='completed' AND date BETWEEN ...`）。
- [ ] Given prompt 约束，When 生成 SQL，Then prompt 含禁止 `SELECT *`、要求 `LIMIT ≤ 1000` 的限制语句。
- [ ] Given LLM 返回非 SQL 内容，When 解析，Then 回退到安全处理（需要安全校验拦截，或在生成器内做格式过滤）。
- [ ] Given 标准化值传递失败（`None`），When 生成 SQL，Then 不注入该值的 WHERE 条件（不破坏 SQL 语法）。
- [ ] 生成器输出 SQL 字符串 + confidence + 解释文本。

## Blocked by

- #2（需语义匹配结果 + NormalizedValue 作 prompt 输入）

## Notes

- LLM prompt 使用现有 `llm/client.py`（create_llm_caller）；system prompt 含 schema 描述 + 约束规则。
- 单步约束：prompt 中要求「只生成单表查询」。安全校验（#4）会进一步拦截多表 SQL。
- 测试可 mock LLM 返回固定 SQL。

## Publish Status

- Status: created
- Updated At: 2026-06-19T06:59:46Z
- GitHub Number: 32
- GitHub URL: https://github.com/yanheng799/chat-db/issues/32
