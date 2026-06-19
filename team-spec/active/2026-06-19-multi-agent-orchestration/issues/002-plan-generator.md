# 实现多步查询计划生成——检测多步信号、查询图谱 JOIN 路径、拆解子任务 DAG

## Parent

PRD：`team-spec/active/2026-06-19-multi-agent-orchestration/prd/prd.md`（6.3 计划生成，issue B）

## What to build

实现计划生成 Agent：当路由判定为多步后，调用 Phase 3 `shortest_join_path` 获取 JOIN 路径（不传 `min_confidence`）；结合多步信号（MULTI_STEP_PATTERNS 正则命中类型）与 JOIN 路径信息，拆解用户查询为子任务 DAG（每个子任务含表名/列名/时间窗口/聚合/条件）。子任务间的依赖：时间窗口对比→并行；JOIN 路径→按路径顺序串行。输出 DAG 结构 `[{id, type, params, dependencies}]`。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given 「对比本月和上月的销售额」→ 拆为 2 个并行子任务（本月销售额 + 上月销售额），无依赖。
- [ ] Given 「包含客户名的已完成订单」+ 图谱有 orders↔customers JOIN 路径 → 拆为含 JOIN 路径的子任务。
- [ ] Given 两表无 JOIN 路径 → 生成单表子任务（不硬造路径）。
- [ ] 输出 DAG 结构含 `{id, type, params, dependencies}`，可被 DAG 执行器消费。
- [ ] 子任务依赖关系正确：时间对比并行、JOIN 路径串行、不相关分支无依赖。

## Blocked by

- #1（需状态图节点定义）

## Notes

- 图谱集成：直接调 Phase 3 `shortest_join_path(graph_store, ds_id, table_a, table_b)`，返回 `[{from_table, from_column, to_table, to_column, type, confidence}]`。
- MULTI_STEP_PATTERNS 来自 #1 的路由判定，本 issue 消费其检测结果做拆解。
- 测试 mock Phase 3 图谱 + mock 语义匹配结果。

## Publish Status

- Status: created
- Updated At: 2026-06-19T07:30:02Z
- GitHub Number: 38
- GitHub URL: https://github.com/yanheng799/chat-db/issues/38
