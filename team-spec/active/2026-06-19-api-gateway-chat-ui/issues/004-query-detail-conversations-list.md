# 补全 query 历史详情和 conversations 列表端点

## Parent

PRD：`team-spec/active/2026-06-19-api-gateway-chat-ui/prd/prd.md`（Phase 9 端点缺口）

## What to build

开发计划 Phase 9 端点表列了但未实现的两个端点：
- `GET /api/query/{id}`：返回单次查询的详情（原始 SQL、结果摘要、执行耗时、标准化值、语义匹配结果）。
- `GET /api/conversations`：返回当前用户的所有会话列表（按最近活动时间倒序）。当前只有 `GET /api/conversations/{session_id}`（单会话历史），缺列表端点。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] `GET /api/query/{id}` → 返回查询详情（sql、summary、execution_time_ms、need_confirm_items）。
- [ ] `GET /api/conversations` → 返回会话列表 `[{session_id, last_message, last_activity}]`。
- [ ] 查询详情端点在查询不存在时返回 404。

## Blocked by

- None

## Publish Status

- Status: created
- Updated At: 2026-06-19T08:42:35Z
- GitHub Number: 59
- GitHub URL: https://github.com/yanheng799/chat-db/issues/59
