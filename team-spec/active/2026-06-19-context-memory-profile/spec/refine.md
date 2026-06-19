# 上下文记忆与用户特征（Phase 8）— 规格细化

- **slug**：`2026-06-19-context-memory-profile`
- **状态**：refining 完成（第 4 轮，核心行为已定，待 `team-spec-review` 复查）
- **基线**：设计文档 §十一 用户特征系统 + §三 3.1 上下文记忆；开发计划 Phase 8（8.1–8.5）
- **依赖**：Redis（已在 .env.example 配置）、Phase 9 认证系统未实现（V1 基于匿名 Session ID）

## 需求复述

让系统「记住」用户——短期会话记忆（多轮对话不丢上下文）、查询结果缓存（相同问题秒回）、长期摘要（对话压缩存档）、用户特征（技能水平/常用表/术语习惯/时间偏好异步学习）。V1 基于匿名 Session ID（Phase 9 认证后迁移到 `user_id`）。

## 范围内（本规格）

- **8.1 会话管理**：Session ID 生成（UUID）→ Redis 存储最近 N 轮对话 → LLM 上下文构建。
- **8.2 查询结果缓存**：Redis TTL 5 分钟，Key = `query_cache:{hash(normalized_query)}`。
- **8.3 长期摘要**：对话结束时 LLM 异步摘要（关键信息→ PG `conversation_summaries`）。
- **8.4 用户特征记录 Agent**：异步推断——技能水平/常用表频率/术语习惯/时间偏好。
- **8.5 用户画像存储**：PG `user_profiles` + `user_table_preferences` + `user_term_mappings`。

## 范围外 / 延期

- 真实用户认证系统（Phase 9）。
- 结果缓存的多用户共享策略（V1 仅同 Session 缓存）。

## 行为规格 — 会话/缓存（已定）

- **会话 TTL**：30 分钟无活动过期（Redis `EXPIRE`）。
- **缓存**：仅同 Session 内共享（Key = `query_cache:{session_id}:{hash}`），V1 不跨 Session。
- **LLM 上下文**：最近 **10 轮对话**，**全量原文**保留（用户问→系统答完整记录）。

## 行为规格 — 摘要/特征触发（已定）

- **长期摘要**：对话结束 → 异步任务 → LLM 摘要 → PG `conversation_summaries`。不阻塞查询响应。
- **用户特征记录**：每次查询后异步暂存原始数据到 Redis → 定时批量（每 5 分钟）聚合统计 → PG 画像表。

## 行为规格 — 画像表 schema（已定）

- **`user_profiles`**：`session_id(VARCHAR PK), skill_level(VARCHAR, default='beginner'), time_preference(VARCHAR, default='30d'), created_at`
- **`user_table_preferences`**：`session_id, table_name, query_count(INT, default=1)`。唯一约束 `(session_id, table_name)`，`ON CONFLICT UPDATE query_count+1`。
- **`user_term_mappings`**：`session_id, user_term, corrected_term, created_at`

## 验收口径

**应通过**：
- 同一 Session 内连续问 3 个相关问题 → LLM 上下文含前 2 轮历史 → 回答利用了上下文。
- 同一 Session 内问「昨天的订单总数」两次 → 第二次命中 Redis 缓存 → 响应时间 < 1s（不调 LLM/SQL）。
- Session 过期 30 分钟后历史清除 → 新一轮对话不包含历史上下文。
- 一次查询后异步写入表偏好（`query_count` 递增）。
- 对话结束后异步生成摘要 → PG `conversation_summaries` 可查询到。

**应失败/边界**：
- Redis 不可用（启动时或运行时挂掉）→ 会话/缓存/特征暂存降级跳过，不影响查询本身。
- 不同 Session ID 的缓存不互相命中（隔离）。

## 轻量风险扫尾

- **无 P0**。
- **P1**：Redis 是会话+缓存+特征暂存的唯一依赖——Redis 挂掉时整个记忆层静默降级（无历史+无缓存+特征延迟），V1 可接受但有用户感知的体验退化。
- **P2**：匿名 Session ID 在 Phase 9 认证完成后需迁移到 `user_id`——画像表和摘要表的关联字段需要改变。V1 用 `session_id`，迁移时新增 `user_id` 列并批量回填。
- **P2**：LLM 上下文 10 轮全量可能导致 token 超出上下文窗口——需在构建时截断（如每轮限制 500 tokens，超出截尾）。
- **P3**：Redis 缓存 TTL 5min 与 Session TTL 30min 的协同——缓存可能比会话先生效，正常。

## 开放问题（均已决议或转延期）

1. ~~范围~~ → 方案 B（全 5 子领域）。
2. ~~会话/缓存~~ → 30min + 同 Session + 10 轮全量。
3. ~~摘要/特征触发~~ → 方案 A（两者异步）。
4. ~~画像 schema~~ → 方案 A（三表 + increment + 唯一约束）。
5. **延期项**：真实用户 ID 迁移（Phase 9）。

## Change Log

- 2026-06-19（第 1 轮）：确认范围 = 方案 B（全 5 子领域）。
- 2026-06-19（第 2 轮）：确认会话/缓存 = 30min TTL + 同 Session 缓存 + 10 轮全量。
- 2026-06-19（第 3 轮）：确认摘要/特征触发 = 方案 A（两者异步）。
- 2026-06-19（第 4 轮）：确认画像 schema = 方案 A（三表 + increment + 唯一约束）。补全验收口径、风险扫尾。