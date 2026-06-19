# 实现长期摘要——对话结束异步 LLM 摘要→PG

## Parent

PRD：`team-spec/active/2026-06-19-context-memory-profile/prd/prd.md`（8.3）

## What to build

会话结束时（30min TTL 过期或用户主动结束）→ 异步触发 LLM 摘要任务：输入 = 最近 10 轮对话全量原文，输出 = 简短中文摘要（关键信息：查询了什么表、什么条件、有什么偏好）。摘要存入 PG `conversation_summaries` 表。Alembic 迁移含该表。异步队列不阻塞查询。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] 对话结束 → 异步生成摘要 → PG `conversation_summaries` 有新记录。
- [ ] 摘要含关键字段（表名、时间条件、业务偏好）。
- [ ] 迁移可正反向。

## Blocked by

- None

## Publish Status

- Status: created
- Updated At: 2026-06-19T08:09:32Z
- GitHub Number: 47
- GitHub URL: https://github.com/yanheng799/chat-db/issues/47
