# 补全热词词典和固定日期周期的增删改端点

## Parent

PRD：`team-spec/active/2026-06-19-admin-api/prd/prd.md`（Phase 10.4+10.5 CRUD 缺口）

## What to build

admin.py 的 `/api/admin/hotwords` 和 `/api/admin/fixed-periods` 当前只读（仅有 GET）。补全增删改：
- `POST /api/admin/hotwords`：添加热词（term, target_table, target_column, formula?, locked?）。
- `DELETE /api/admin/hotwords/{term}`：删除热词。
- `POST /api/admin/fixed-periods`：添加固定日期周期（name, start_mmdd, end_mmdd）。
- `DELETE /api/admin/fixed-periods/{name}`：删除周期。

V1 存储：hotwords 操作内存字典（`semantic.hot_words.HOT_WORDS`）+ 持久化到配置文件；fixed-periods 操作内存字典（`normalizer.time_parser.FIXED_DATE_PERIODS`）+ 持久化。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] `POST /api/admin/hotwords` 添加热词后 `GET` 可见。
- [ ] `DELETE /api/admin/hotwords/{term}` 删除后 `GET` 不再包含。
- [ ] `POST/DELETE /api/admin/fixed-periods` 同样可测试。
- [ ] 重启服务后增删结果保留（持久化到 PG 或配置文件）。

## Blocked by

- None

## Publish Status

- Status: created
- Updated At: 2026-06-19T08:42:36Z
- GitHub Number: 60
- GitHub URL: https://github.com/yanheng799/chat-db/issues/60
