# 实现会话管理+查询结果缓存——Redis 10轮上下文+TTL

## Parent

PRD：`team-spec/active/2026-06-19-context-memory-profile/prd/prd.md`（8.1+8.2）

## What to build

会话管理：生成 UUID Session ID → Redis `HSET` 存储最近 10 轮对话（全量原文）→ 30min TTL → LLM 调用时注入上下文（每轮 ≤500 tokens 截断）。查询结果缓存：标准化查询 hash → Redis `GET query_cache:{session_id}:{hash}`，TTL 5min，仅同 Session 命中。Redis 不可用→静默降级。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] 同 Session 连续 3 问 → 第 3 问的 LLM 上下文包含前 2 问历史。
- [ ] 同 Session 重复问同一标准化查询 → 第 2 次命中缓存，响应 <1s。
- [ ] Session 30min 过期 → 新一轮查询无历史上下文。
- [ ] Redis 不可用 → 查询正常返回，无崩溃。

## Blocked by

- None

## Notes

- Redis 客户端 `redis-py`（需检查 pyproject 是否已声明）。
- 上下文截断：每轮 >500 tokens 时截尾。

## Publish Status

- Status: created
- Updated At: 2026-06-19T08:09:29Z
- GitHub Number: 46
- GitHub URL: https://github.com/yanheng799/chat-db/issues/46
