# 以只读方式执行校验通过的 SQL 并捕获结果

## Parent

PRD：`team-spec/active/2026-06-19-semantic-matching-pipeline/prd/prd.md`（5.4 SQL 执行，issue E）

## What to build

实现 SQL 执行器：通过 Phase 2 `query_executor` 抽象（只读连接 + `SET TRANSACTION READ ONLY` + `statement_timeout`）执行安全校验通过的 SQL，捕获结果（列名 + 数据行）并记录执行耗时。超时/错误 → 捕获异常、返回错误信息（含原因和原始 SQL），V1 不做自动修正（自愈延 Phase 7）。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given 一条合法 SELECT 语句，When 执行，Then 返回 `{columns: [...], rows: [...], execution_time_ms: N}`。
- [ ] Given SQL 执行超时，When 执行，Then 捕获超时异常、返回 `{error: "timeout", original_sql: "..."}`。
- [ ] Given SQL 执行报错（如语法错误），When 执行，Then 捕获错误、返回错误信息（含错误详情 + 原始 SQL）。
- [ ] 执行器在目标库上设置 `SET TRANSACTION READ ONLY` + `statement_timeout`。
- [ ] 结果中不含连接凭据或内部状态（只返回数据列+行）。

## Blocked by

- None - can start immediately

## Notes

- 复用 Phase 2 `query_executor` 抽象（`metadata.extractor` 或新建独立执行器）。
- `statement_timeout` 复用配置文件（`learning_job_timeout_minutes` 或新增查询级超时配置）。
- V1 不做 SQL 重试/自愈（延 Phase 7）。

## Publish Status

- Status: created
- Updated At: 2026-06-19T06:59:51Z
- GitHub Number: 34
- GitHub URL: https://github.com/yanheng799/chat-db/issues/34
