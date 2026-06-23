# Issue 1 — 把历史会话持久化到 PostgreSQL，重启后仍可回看

## Parent

PRD：`team-spec/active/2026-06-23-conversation-history-persistence/prd/prd.md`（历史会话持久化）

## What to build

端到端最小闭环：把对话历史从 Redis 持久化到应用 PostgreSQL，使其在 Redis TTL 过期与服务重启后仍可**列表与详情回看**。

- 新增 **Alembic 迁移**，建 `chat_conversations` 与 `chat_messages` 两表（字段见 PRD §数据与状态；`chat_messages.result` 为 JSONB 存全量 `{columns, rows, execution_time_ms}`）。
- 在 `gateway.py` 现有 `add_turn` 调用处，**异步 fire-and-forget** 双写一条 PG 消息：含 `user_text`、`assistant_summary`、`sql`、完整 `result`、`status` 快照（`success`/`error`/`need_confirm`/`empty`/`dry_run`）、`error`、`data_source_id`、`seq`、`created_at`。**所有查询尝试都写**（沿用 `add_turn` 在 `finally` 对全部结果调用的现状），按结果打 `status`。
- 把 `GET /api/conversations`（列表）与 `GET /api/conversations/{sid}`（详情）**改为读 PG**，带基础分页（`limit`/`offset` + 按 `last_message_at` 倒序）。
- **不改动** SSE 查询主流程与 Redis 热上下文行为（`get_context` 仍读 Redis 最近若干轮）。Redis 继续作为热上下文层不变；PG 仅作冷历史层。
- 实现注意：现有 `add_turn(sid, user_text, assistant_text, sql)` 只传 `summary`/`sql`，未带完整 `result`；双写需把 `result["result"]`（`columns`/`rows`）一并传入持久化调用——该变量在 `_run_pipeline` 作用域内可见。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given 用户完成一次成功查询，When 服务重启且 Redis 30min TTL 过期，Then `GET /api/conversations` 仍列出该会话，`GET /api/conversations/{sid}` 返回提问 / SQL / 完整结果（行列一致）。
- [ ] Given 一次报错查询，When 查看历史，Then 该消息 `status=error` 且含错误信息。
- [ ] Given 一次 `need_confirm` 查询，When 查看历史，Then 该消息 `status=need_confirm` 且含 SQL。
- [ ] Given 一次返回 N 行的查询，When 查看历史结果，Then `rows` 行数 = N（全量不截断）。
- [ ] Given PG 写入失败（模拟），When 用户查询，Then 实时结果正常返回、延迟不显著上升、仅日志记录（异步不阻塞热路径）。
- [ ] Given 多轮追问，When LLM 构建上下文，Then 仍取 Redis 最近若干轮（热上下文行为不变）。
- [ ] 历史列表带分页（`limit`/`offset`）与按 `last_message_at` 倒序排序。
- [ ] Alembic 迁移可成功 `upgrade` 与 `downgrade`。
- [ ] 相关自动化或手工验证路径明确（参考 `test/` 下 `test_config` / `test_metadata` 模式，测外部行为）。

## Blocked by

- None — 可立即开始

## Notes

- **架构决策**：分层（Redis 热 + PG 冷），异步 fire-and-forget 双写，不阻塞查询热路径；PG 写失败仅记日志、不回滚 Redis（历史 best-effort，R5）。
- **实现模式**：与现有 app-DB 业务表一致（raw `text()` SQL，见 `src/profile/models.py`、`src/memory/summarizer.py`），或全局统一 ORM——实现时择一并与现有模式保持一致（PRD 开放问题 6）。
- 表名用 `chat_` 前缀以区别已实现的 `conversation_summaries`。
- `status` 为写入时**快照标签**，不做状态流转（现有 `confirm` 端点为 stub，`need_confirm` 不会转 `success`，R9）。
- 一个会话可跨多 `data_source`；每条消息记 `data_source_id`。
- **已接受风险（scope-conditional）**：全量业务结果明文沉淀、不脱敏（R2）——前提内部 / 受控部署；仅手动清理、无自动任务（R1）——本期不实现自动保留期清理。
- **可选顺带项**（非硬性验收）：`GET /api/query/{id}` 现读进程内存 `_query_store` dict（重启即丢），可顺带改读 PG（PRD 开放问题 3）。

## Publish Status

- Status: created
- Updated At: 2026-06-23T13:39:40Z
- GitHub Number: 70
- GitHub URL: https://github.com/yanheng799/chat-db/issues/70
