# 实现跨表字段自愈——向量搜索+图谱 JOIN+自动构建 JOIN 查询

## Parent

PRD：`team-spec/active/2026-06-19-error-self-healing/prd/prd.md`（7.3 跨表字段自愈）

## What to build

当列不存在且跨表候选命中时：调用 Phase 3 向量检索全局搜索该字段名 → 按 score>0.7 过滤非本表的候选字段 → 对每个候选调用 Phase 3 `shortest_join_path` 查 JOIN 路径 → 找到路径 → 自动构建含 JOIN 的 SQL 查询并执行。流程复用 Phase 6 `execute_dag` 做编排。Phase 3 调用含超时参数；超时→降级跳过跨表策略→下一策略。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given 字段在 orders 中不存在但 customers 中有该字段，且图谱有 JOIN 路径 → 自动构建 `SELECT ... FROM orders JOIN customers ...` → 重试成功。
- [ ] Given 向量搜索无候选（score<0.7）→ 不触发跨表修复 → 进入 `other`。
- [ ] Given 图谱无 JOIN 路径 → 返回候选列表（不硬造 JOIN）。
- [ ] Given Phase 3 向量搜索超时 → 降级跳过跨表策略 → 进入下一策略。
- [ ] 跨表修复流程复用 Phase 6 `execute_dag`（拓扑排序+执行+降级）。

## Blocked by

- Phase 3（`search_fields` + `shortest_join_path`，PR #22，已实现）
- Phase 6（`execute_dag`，PR #40，已实现）

## Notes

- 向量检索复用 Phase 3 `search_fields`；图谱 JOIN 复用 `shortest_join_path`。
- 跨表自愈作为 LangGraph 状态图的 `healing_agent` 子图中的一个节点。

## Publish Status

- Status: created
- Updated At: 2026-06-19T07:49:59Z
- GitHub Number: 43
- GitHub URL: https://github.com/yanheng799/chat-db/issues/43
