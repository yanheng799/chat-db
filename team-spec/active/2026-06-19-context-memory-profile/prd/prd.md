# 上下文记忆与用户特征（Phase 8）— 会话管理 + 缓存 + 画像 + 异步学习

## 问题陈述

Phase 5-7 每次查询都是「无状态」的——不记得上一轮说了什么、不记得用户偏好、不缓存重复查询。真实的对话式查询需要上下文（「上一个问题的基础上再问」）、需要缓存（相同问题秒回）、需要个性化（新手要详解、老手要简洁）。Phase 8 用 Redis 做会话记忆+结果缓存，PG 做长期画像，异步 Agent 做用户特征学习。V1 基于匿名 Session ID（Phase 9 认证后迁移到真实 user_id）。

## 目标

- 同一 Session 内 10 轮对话保持上下文连贯。
- 同 Session 内相同标准化查询命中 Redis 缓存（<1s 响应）。
- 对话结束后生成 LLM 长期摘要存入 PG。
- 异步 Agent 记录用户表偏好、术语习惯、技能水平。

## 非目标

- 真实用户认证系统（Phase 9）。
- 跨 Session 全局共享缓存（V1 仅同 Session）。
- 用户特征的实时查询建议（V1 只记录，查询建议延 Phase 11）。

## 用户与场景

1. 连续追问「查一下昨天的订单总数」「其中已完成的多少」→ 系统利用上下文知道「其中」指「昨天的订单中」。
2. 重复问「昨天的订单总数」→ 命中缓存，<1s 返回（不调 LLM/SQL）。
3. 新用户首次查询 → 默认新手技能水平 → 结果解释更详细。

## 当前状态

- Redis 已启动 + 已配置 `.env.example`。
- Phase 5/6 管道已实现。
- **缺口**：`src/memory/`、`src/profile/` 为空。

## 方案描述

**会话**：用户连接时生成 UUID Session ID → Redis `HSET` 存储最近 10 轮对话 → LLM 调用时注入上下文。

**缓存**：标准化查询 hash → Redis `GET query_cache:{session_id}:{hash}`，命中直接返回，TTL 5min。

**摘要**：对话结束 → 异步任务 → LLM 摘要 → PG `conversation_summaries`。

**特征**：每次查询后异步记录原始数据到 Redis → 定时批量（5min）聚合 → PG 三表。

## 范围

### 范围内

- 8.1–8.5 全部（会话、缓存、摘要、特征记录、画像存储）

### 范围外

- 真实用户 ID（Phase 9）、跨 Session 缓存、实时查询建议

## 功能需求

1. 系统必须生成匿名 Session ID 并管理 Redis 会话（最近 10 轮，与 30min TTL）。
2. LLM 调用必须注入当前会话历史作为上下文。
3. 系统必须缓存同 Session 内的标准化查询结果（Redis TTL 5min）。
4. 会话结束（过期/主动）须异步生成 LLM 摘要→ PG `conversation_summaries`。
5. 每次查询后须异步记录表偏好（`query_count+1`）。
6. 系统必须定时批量聚合用户特征（技能/常用表/术语/时间偏好）。
7. Redis 不可用时所有记忆功能静默降级，不影响查询本身。

## 业务规则

- Session TTL 30min，缓存 TTL 5min。
- 仅同 Session 缓存；10 轮全量上下文（每轮 ≤500 tokens 截断）。
- 摘要+特征均异步队列，不阻塞查询。
- 画像增量更新：`query_count ON CONFLICT UPDATE +1`。

## 数据与状态

- **Redis**：`session:{id}` (hash, 10 轮历史)、`cache:{session}:{hash}` (string, TTL 5min)
- **PG**：`conversation_summaries`、`user_profiles`、`user_table_preferences`、`user_term_mappings`

## 实现决策

- 模块：`src/memory/`（session/cache/summarizer）、`src/profile/`（feature_agent + models）
- Redis 客户端：`redis-py`（已声明？需检查 pyproject）
- Phase 9 迁移：预留 `user_id` 列，当前用 `session_id`

## 验收标准

- 同 Session 连续 3 问 → 第 3 问利用前 2 问上下文。
- 同 Session 重复问 → 第 2 次命中缓存 <1s。
- Session 过期 30min → 新查询无历史。
- 查询后表偏好 query_count 递增。
- Redis 挂掉 → 查询正常返回，无崩溃。

## 开放问题

- `redis-py` 是否已在 pyproject.toml 声明。
- Phase 9 user_id 迁移策略。

## 预拆 issue

A 会话管理 + 缓存、B 长期摘要、C 用户画像存储 + 迁移、D 用户特征记录 Agent。A→C/D 并行→B（独立）
