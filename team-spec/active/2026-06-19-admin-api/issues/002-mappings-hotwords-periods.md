# 实现值映射、热词词典和固定日期周期 CRUD 管理端点

## Parent

PRD：`team-spec/active/2026-06-19-admin-api/prd/prd.md`（10.3+10.4+10.5）

## What to build

值映射 CRUD：`GET/POST/PUT/DELETE /api/admin/mappings/enum|region|name`（复用 Phase 4 mapping_service）。热词 CRUD：`GET/POST/PUT/DELETE /api/admin/hotwords`（管理热词词典）。固定日期 CRUD：`GET/POST/PUT/DELETE /api/admin/fixed-periods`（管理双十一/618 等周期）。

## Type

AFK

## Acceptance criteria

- [ ] 枚举/区域/名称映射 CRUD 全部可测试。
- [ ] 热词词典增删改查正常。
- [ ] 固定日期周期 CRUD 正常。

## Blocked by

- None

## Publish Status

- Status: created
- Updated At: 2026-06-19T08:27:15Z
- GitHub Number: 56
- GitHub URL: https://github.com/yanheng799/chat-db/issues/56
