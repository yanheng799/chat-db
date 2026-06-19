# 实现同步状态查询和图谱数据导出管理端点

## Parent

PRD：`team-spec/active/2026-06-19-admin-api/prd/prd.md`（10.1+10.2）

## What to build

`GET /api/admin/sync/status`（最近同步时间+状态）、`GET /api/admin/sync/logs`（同步变更记录）、`POST /api/admin/sync/trigger`（手动触发全量同步）。`GET /api/admin/graph/nodes/{ds}` 和 `GET /api/admin/graph/edges/{ds}`（导出图谱数据）。

## Type

AFK

## Acceptance criteria

- [ ] sync/status 返回最近同步日志的状态。
- [ ] sync/logs 返回分页变更记录。
- [ ] sync/trigger 触发同步并返回任务 ID。
- [ ] graph/nodes/{ds} 返回该源 Table/Column 节点。
- [ ] graph/edges/{ds} 返回 CONTAINS/REFERENCES/INFERRED_REF 边。

## Blocked by

- None

## Publish Status

- Status: created
- Updated At: 2026-06-19T08:27:13Z
- GitHub Number: 55
- GitHub URL: https://github.com/yanheng799/chat-db/issues/55
