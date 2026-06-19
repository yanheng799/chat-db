# 构建 LangGraph 状态图并实现单步/多步路由判定

## Parent

PRD：`team-spec/active/2026-06-19-multi-agent-orchestration/prd/prd.md`（6.1 状态图，issue A）

## What to build

构建 LangGraph 状态图入口：定义 State Schema（`{nl_text, data_source_id, route, plan, results, summary, need_confirm_items, error}`）；实现 `classify_query` 首节点做纯规则路由判定（不调 LLM）：(1) MULTI_STEP_PATTERNS 正则检测多步信号，(2) 若语义匹配识别 >1 表 + Phase 3 `shortest_join_path` 确认 JOIN 路径 → 路由到多步计划生成；以上均不满足 → 路由到 Phase 5 `run_single_step`（单步通道）。定义条件边：单步 → Phase 5 节点、多步 → 计划生成节点。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given 「查昨天的订单总数」→ `classify_query` 判定为单步，路由到 Phase 5。
- [ ] Given 「对比本月和上月的销售额」→ 正则命中多步信号，路由到计划生成。
- [ ] Given 「包含客户名的已完成订单」且图谱有 JOIN 路径 → 路由到计划生成。
- [ ] Given 单一简单查询 + 单表无 JOIN → 路由到单步。
- [ ] State Schema 定义完整，各节点可读写共享状态。
- [ ] 状态图可运行（dry-run），条件边触发正确。

## Blocked by

- None

## Notes

- `langgraph` 已在 pyproject；`src/agents/` 从零建。
- MULTI_STEP_PATTERNS 沿用 dev 计划预设（对比/比较/变化/先…再/然后/同时查）+ 图谱检测。
- 测试可用 mock Phase 5 `run_single_step` 和 mock Phase 3 `shortest_join_path`。

## Publish Status

- Status: created
- Updated At: 2026-06-19T07:29:59Z
- GitHub Number: 37
- GitHub URL: https://github.com/yanheng799/chat-db/issues/37
