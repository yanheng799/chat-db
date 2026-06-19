# API Gateway + Web Chat UI（Phase 9）— 规格细化

- **slug**：`2026-06-19-api-gateway-chat-ui`
- **状态**：refining 完成（第 3 轮，核心行为已定，待 `team-spec-review` 复查）
- **基线**：设计文档 §二 2.1 用户交互层；开发计划 Phase 9

## 需求复述

Phase 5-8 建了完整后端能力（查询管道+语义匹配+值标准化+多步编排+错误自愈+上下文记忆），但全是通过 Python 函数调用的——没有统一的外部 API 入口。Phase 9 构建 FastAPI Gateway 统一端点（query、confirm、conversations、session），让外部系统能通过 REST/SSE 调用全部能力。

## 范围内

- 9.1 API Gateway（FastAPI 统一端点 + SSE 流式 + 请求/响应模型 + 错误处理 + CORS）
- 9.6 前后端联调（端到端验证场景——但有 API 无 UI，联调用脚本/curl 代替）

## 范围外 / 延期

- Next.js 前端（9.2-9.5 全部延期 Phase 10）
- 聊天界面 / 结果展示 / 审核交互—— Phase 10

## 行为规格 — 端点设计（已定）

| 端点 | 方法 | 说明 |
|------|------|------|
| `POST /api/query` | POST | 提交 NL 查询 → SSE 流式（status/result/need_confirm/error/done 事件） |
| `POST /api/query/{id}/confirm` | POST | 用户确认 → 继续管道执行 |
| `POST /api/query/{id}/cancel` | POST | 取消等待中的查询 |
| `POST /api/session` | POST | 创建新会话 → 返回 `session_id` |
| `GET /api/conversations/{session_id}` | GET | 会话历史 |
| `GET /api/health` | GET | 健康检查 |

SSE 事件：`status`(管道进度)、`result`(查询结果)、`need_confirm`(待确认项)、`error`(错误)、`done`(流结束)。

## 行为规格 — Session/认证（已定）

- **自动创建**：首次查询无 `X-Session-Id` → 自动创建 Session + 返回 header。
- **Header 传递**：后续查询带 `X-Session-Id` 复用会话。
- **V1 无认证**：不设 API Key（内网/本地运行）。Phase 10 加认证。

## 验收口径

- `POST /api/query` {"text":"昨天的订单总数"} → 返回 SSE 流（status→result→done）。
- 无 `X-Session-Id` → 自动创建 + 响应 header 含 `X-Session-Id`。
- `POST /api/query/{id}/confirm` → 继续管道执行。
- `GET /api/conversations/{session_id}` → 返回该会话历史。
- `GET /api/health` → 200。

## 轻量风险扫尾

- **无 P0**。P1：SSE 流式的超时与断线重连（前端未建，V1 用 curl/脚本测试——不做重连）。
- P2：无认证 → 任何能访问端口的人都能调 API（V1 内网接受）。

## 开放问题（均已决议）

1. ~~范围~~ → C（纯 API）。
2. ~~端点~~ → B（6 端点 + 5 SSE 事件）。
3. ~~Session~~ → A（自动创建 + Header + 无认证）。

## Change Log

- 第 1 轮：确认范围 = 方案 C。
- 第 2 轮：确认端点 = 方案 B。
- 第 3 轮：确认 Session = 方案 A。收尾。