# 实现用户特征记录 Agent——异步记录+定时批量聚合

## Parent

PRD：`team-spec/active/2026-06-19-context-memory-profile/prd/prd.md`（8.4）

## What to build

用户特征记录 Agent：每次查询后异步将原始数据暂存 Redis → 定时批量（每 5 分钟）聚合统计——技能水平（新/中/高级推断）、常用表（频次 count）、术语习惯（纠正反馈记录）、时间偏好（无时间词时的默认范围）。聚合结果写入 PG 画像表。Redis 暂存数据 TTL 10min（比 Session TTL 短，不累积过期会话）。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] 查询后暂存数据到 Redis（{session_id}:pending_features）。
- [ ] 定时任务每 5min 批量聚合并写入 PG 画像表。
- [ ] 表偏好 `query_count` 正确递增。
- [ ] Redis 不可用→暂存跳过，不影响查询。

## Blocked by

- #3（需画像表）

## Publish Status

- Status: created
- Updated At: 2026-06-19T08:09:37Z
- GitHub Number: 49
- GitHub URL: https://github.com/yanheng799/chat-db/issues/49
