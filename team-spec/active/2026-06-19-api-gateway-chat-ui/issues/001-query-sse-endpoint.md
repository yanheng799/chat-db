# 实现 POST /api/query SSE 流式查询端点

## Parent

PRD：`team-spec/active/2026-06-19-api-gateway-chat-ui/prd/prd.md`

## What to build

`POST /api/query` 端点：接收 `{text, session_id?}`→ 调 Phase 5/6 管道 → SSE 流式返回（status/result/need_confirm/error/done 事件）。无 session_id 自动创建 + header `X-Session-Id`。CORS `*`。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] curl POST `/api/query {"text":"昨天的订单总数"}` → SSE 流返回结果。
- [ ] 无 session_id → 自动创建 + `X-Session-Id` header。
- [ ] SSE 事件格式：`data: {"type":"status","message":"..."}` 等。

## Blocked by

- None

## Publish Status

- Status: created
- Updated At: 2026-06-19T08:21:03Z
- GitHub Number: 51
- GitHub URL: https://github.com/yanheng799/chat-db/issues/51
