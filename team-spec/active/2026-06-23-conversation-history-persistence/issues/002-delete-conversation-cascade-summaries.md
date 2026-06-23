# Issue 2 — 删除一条历史会话时彻底清除其消息与会话摘要

## Parent

PRD：`team-spec/active/2026-06-23-conversation-history-persistence/prd/prd.md`（历史会话持久化）；复用 Issue 1 的表与写入路径。

## What to build

端到端删除闭环：用户删除一条历史会话时，**硬删除**其全部消息与全量结果，并**级联清理**同 `session_id` 的 `conversation_summaries`（避免孤儿）。

- 把 `DELETE /api/conversations/{sid}` 改为写 PG：物理删除该 conversation 的所有 `chat_messages`、对应 `chat_conversations` 行，并删除 `conversation_summaries` 中同 `session_id` 的摘要行。
- **hard delete**（不设 `deleted_at`，不可恢复）。
- 幂等：删除不存在的会话返回成功（或 404，实现时定）。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given 用户删除会话 X（X 有消息与 `conversation_summaries` 摘要），When 删除完成，Then `chat_messages` 中 X 的消息、`chat_conversations` 中 X 的行、`conversation_summaries` 中同 `session_id` 的摘要**均不存在**。
- [ ] Given 删除后，When 调用 `GET /api/conversations` 与 `GET /api/conversations/{sid}`，Then X 不再出现 / 返回 404。
- [ ] Given 删除不存在的会话，When 调用 `DELETE`，Then 幂等返回成功（或 404），不报错。
- [ ] 删除只影响目标会话，不影响其他会话及其摘要。
- [ ] 相关自动化或手工验证路径明确。

## Blocked by

- #1（依赖其建表 `chat_conversations` / `chat_messages` 与写入路径）

## Notes

- **删除语义**为 hard delete（与"不脱敏"配套形成"删除即真删"的合规姿态）；不可恢复。
- **级联 `conversation_summaries` 跨工作流**（memory-profile）：确认级联不破坏其画像统计（R6）；未来 Phase 9 迁 `user_id` 时两处需同步。
- `conversation_summaries` 已实现于 `src/memory/summarizer.py`（按 `session_id` 存摘要）。

## Publish Status

- Status: created
- Updated At: 2026-06-23T13:39:44Z
- GitHub Number: 71
- GitHub URL: https://github.com/yanheng799/chat-db/issues/71
