# 实现错误分类器并触发元数据过期同步修复

## Parent

PRD：`team-spec/active/2026-06-19-error-self-healing/prd/prd.md`（7.1 分类器 + 7.2 元数据过期）

## What to build

实现 SQL 执行错误的自动分类与元数据过期修复：解析 DB 错误消息，按 `pgcode`(PG) / `errno`(MySQL) 精确分类为 `table_not_found` / `column_not_found` / `sql_syntax_error` / `type_mismatch` / `other`（精确码优先，正则兜底）。当分类为 `table_not_found` 或 `column_not_found` 时，触发 Phase 1 元数据同步引擎（对该表全量同步或全数据源同步），同步完成后重试原查询一次。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given PG 错误 `relation "xxx" does not exist` → 分类为 `table_not_found`。
- [ ] Given PG 错误 `column "yyy" does not exist` → 分类为 `column_not_found`。
- [ ] Given MySQL 错误 `Table 'db.xxx' doesn't exist` → 分类为 `table_not_found`。
- [ ] Given 无法匹配的错误消息 → 分类为 `other`。
- [ ] Given `table_not_found` → 触发 Phase 1 同步引擎（复用 `metadata.sync` 对该表同步）→ 重试 SQL。
- [ ] Given `column_not_found` → 同样触发同步→重试。
- [ ] 同步本身失败或超时 → 不重试，返回错误。

## Blocked by

- None

## Notes

- 分类器基于 `pgcode`(PG `sqlstate`) / `errno`(MySQL) 字段做精确匹配，实现期需填充码表映射。
- 同步引擎复用 Phase 1 `metadata.sync`（可通过 `_run_metadata_extraction` 或手动同步接口调用）。

## Publish Status

- Status: created
- Updated At: 2026-06-19T07:49:54Z
- GitHub Number: 41
- GitHub URL: https://github.com/yanheng799/chat-db/issues/41
