# 实现 session 创建和 conversations 历史端点

## Parent

PRD：`team-spec/active/2026-06-19-api-gateway-chat-ui/prd/prd.md`

## What to build

`POST /api/session`（创建新会话→`{session_id}`）、`GET /api/conversations/{session_id}`（返回该会话历史消息）。集成 Phase 8 SessionManager。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] `POST /api/session` → `{"session_id":"..."}`。
- [ ] `GET /api/conversations/{session_id}` → 返回历史消息列表。
- [ ] 复用 Phase 8 `SessionManager`。

## Blocked by

- None

## Publish Status

- Status: created
- Updated At: 2026-06-19T08:21:05Z
- GitHub Number: 52
- GitHub URL: https://github.com/yanheng799/chat-db/issues/52
