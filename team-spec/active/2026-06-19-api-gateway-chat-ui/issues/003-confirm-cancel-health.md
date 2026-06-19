# 实现 confirm/cancel/health 端点和错误处理

## Parent

PRD：`team-spec/active/2026-06-19-api-gateway-chat-ui/prd/prd.md`

## What to build

`POST /api/query/{id}/confirm`（接收 `{confirmed:bool}`→继续管道）、`POST /api/query/{id}/cancel`（取消等待）、`GET /api/health`（健康检查）。统一 JSON 错误格式 `{error, detail}`。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] `/api/health` → `{"status":"ok"}`。
- [ ] confirm 端点接收请求并返回确认状态。
- [ ] 统一错误格式。

## Blocked by

- None

## Publish Status

- Status: created
- Updated At: 2026-06-19T08:21:08Z
- GitHub Number: 53
- GitHub URL: https://github.com/yanheng799/chat-db/issues/53
