# API Gateway（Phase 9）— FastAPI 统一端点 + SSE 流式

## 问题陈述

Phase 5-8 建了完整后端能力但全是通过 Python 函数调用的——没有统一外部 API 入口，只能通过 pytest 或脚本调用。Phase 9 构建 FastAPI Gateway，暴露 REST/SSE 端点让外部系统（未来 Phase 10 Chat UI 或第三方）调用全部查询能力。

## 目标

- `POST /api/query` 提交 NL 查询 → SSE 流式返回结果。
- 自动 Session 管理 + 上下文关联。
- 统一错误格式 + CORS。

## 非目标

- Next.js 前端（Phase 10）
- 认证系统（V1 无认证）

## 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `POST /api/query` | POST | 请求体 `{text, session_id?}` → SSE 流式 |
| `POST /api/query/{id}/confirm` | POST | `{confirmed: bool}` → 继续管道 |
| `POST /api/query/{id}/cancel` | POST | 取消等待中的查询 |
| `POST /api/session` | POST | 创建会话 → `{session_id}` |
| `GET /api/conversations/{session_id}` | GET | 返回历史消息列表 |
| `GET /api/health` | GET | `{"status":"ok"}` |

## SSE 事件

`status`(管道阶段)、`result`(查询结果)、`need_confirm`(待确认)、`error`(错误)、`done`(流结束)

## 功能需求

1. 提交查询 → 调 Phase 5/6 管道 → SSE 流式返回。
2. need_confirm 事件 → 前端展示确认 → `POST /confirm` → 继续执行。
3. 无 session_id → 自动创建 + 响应 header `X-Session-Id`。
4. 统一 JSON 错误格式 `{error, detail}`。
5. CORS `*`（V1 开发模式）。

## 实现决策

- `src/api/gateway.py`（新 FastAPI router）。
- 复用 Phase 5/6 管道入口 + Phase 8 SessionManager。
- SSE 用 `sse-starlette` 或 FastAPI `StreamingResponse`。

## 验收标准

- curl `POST /api/query {"text":"昨天的订单总数"}` → SSE 流式输出结果。
- 无 session_id → 自动创建 + header 返回。
- `/api/health` → 200。

## 预拆 issue

A query SSE 端点、B session+conversations、C confirm+cancel+联调。A→C 并行→B
