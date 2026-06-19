# 多 Agent 编排 LangGraph（Phase 6）— 单步/多步路由 + 计划生成 + 多步串联

## 问题陈述

Phase 5 让单步查询跑通了，但真实业务问题往往需要拆解——「对比本月和上月的销售额，按地区排名」需要两个时间窗口 + 多表 JOIN + 聚合对比。Phase 5 遇到多表或复杂句式直接报错。Phase 6 用 LangGraph 状态图区分单步/多步路由，多步时查图谱做 JOIN 路径规划、生成子任务 DAG、按序执行子查询、传递中间结果并做 LLM 摘要。复用 Phase 5 单步模块作为多步 DAG 中的子执行单元。

## 目标

- 用户输入「对比本月和上月的销售额」→ 自动判定多步 → 拆为两个子查询 DAG → 分别执行 → 合并 + 对比摘要。
- 多步执行中某子查询失败 → 不阻断其他不相关分支 → 成功结果正常展示 + 失败标注原因。
- 复用 Phase 5 单步管道（`run_single_step`）作为子执行单元，不重做联合分析 Agent。

## 非目标

- **6.2 联合分析 Agent**（不新建——复用 Phase 5 管道；不合并 LLM 调用）。
- **6.5 可配置审核策略**（需管理端 UI — Phase 10）。
- 错误自愈（Phase 7）、结果缓存（Phase 11）。

## 用户与场景

1. 作为**查询用户**，我说「对比本月和上月的销售额」，系统自动判定多步、生成计划、执行两个子查询、合并对比结果。
2. 作为**查询用户**，我说「包含客户名的已完成订单」，系统经图谱发现 orders↔customers 需 JOIN，生成多步计划。
3. 作为**查询用户**，多步执行中某子查询失败时，系统展示部分成功结果并标注失败原因。

## 当前状态

- **Phase 5**：单步管道已实现（PR #36）——语义匹配+标准化+SQL 生成+安全+执行。`run_single_step` 可作为子执行单元复用。
- **Phase 3**：图谱最短 JOIN 路径已实现（PR #22）——`shortest_join_path` 可直接调用。
- **langgraph** 已在 pyproject.toml。
- **缺口**：`src/agents/` 为空，无 LangGraph 状态图、无计划生成、无 DAG 执行器。

## 方案描述

**主路径**：用户查询进入 LangGraph 状态图 → 首节点 `classify_query` 做两层纯规则判定（MULTI_STEP_PATTERNS 正则 + 图谱 JOIN 检测）：
- 不满足多步条件 → 路由到 Phase 5 `run_single_step`（单步快速通道）。
- 满足多步条件 → 路由到**计划生成 Agent**：查图谱 JOIN 路径 + 拆解子任务 → 生成 DAG → **DAG 执行器**按拓扑序执行子查询（每个子查询复用 Phase 5 单步管道或 SQL 生成+执行） → 子结果传递 → 合并 + LLM 摘要 → 返回。

**DAG 失败**：best-effort，子任务失败 → 标记该节点 failed、跳过依赖它的后继，与它不相关的分支继续。最终汇总含成功结果 + 失败标注。

## 范围

### 范围内

- 6.1 LangGraph 状态图（State Schema + 节点 + 条件边）
- 6.3 计划生成 Agent（规则检测 + 图谱 JOIN + DAG 拆解）
- 6.6 多步查询串联（DAG 执行器 + 中间结果传递 + LLM 摘要）

### 范围外

- 6.2/6.4 联合分析 / 执行审核 Agent（复用 Phase 5）
- 6.5 审核策略配置（Phase 10）
- 错误自愈（Phase 7）、结果缓存（Phase 11）

## 功能需求

1. 系统必须提供 LangGraph 状态图入口，区分单步/多步路由。
2. 首节点 `classify_query` 必须用 MULTI_STEP_PATTERNS 正则 + 图谱 JOIN 检测做路由判定（不调 LLM）。
3. 多步判定成立时系统必须调 Phase 3 `shortest_join_path` 查 JOIN 路径。
4. 系统必须将多步查询拆为子任务 DAG。
5. 系统必须按拓扑序执行子任务，每个子任务复用 Phase 5 `run_single_step` 或独立 SQL 生成+执行。
6. 系统必须在子任务间传递结构化中间结果（`{columns, row_count, aggregates}`）。
7. DAG 某子任务失败时必须不阻断不相关分支、继续执行；最终结果含成功 + 失败标注。
8. 系统必须在执行前对 DAG 做拓扑排序检测，无法拓扑（有环）→ 拒执行 + 告警。
9. 多步最终结果必须经 LLM 做自然语言摘要（仅对聚合子结果——与 Phase 5 治理一致）。

## 业务规则

- **路由判定**：规则检测（正则命中多步信号）→ 多步；语义匹配识别 >1 表且有 JOIN 路径 → 多步；其他 → 单步。
- **DAG 执行**：best-effort + 子节点失败不阻断不相关节点。
- **摘要治理**：仅对聚合子结果（COUNT/SUM/AVG）做 LLM 自然语言包装；行级结果不传入摘要 LLM。
- **LLM 管控**：多步查询额外消耗计划生成+摘要 2 次 LLM 调用，合并入 `pipeline_llm_max_calls` 上限池（默认沿用 Phase 5 的 5 次）。
- **中间结果格式**：`{columns: [...], row_count: N, aggregates: {col: value}}`。

## 边界情况与错误状态

- 空输入 → 拒绝。
- 路由均不触发 → 默认走单步（Phase 5）。
- 计划生成的 DAG 有环 → 拒执行 + 告警。
- DAG 全部子任务失败 → 返回错误。
- 图谱无 JOIN 路径的两表 → 计划生成只出单表子任务。
- 子结果传递时前一步返回空 → 后一步用空上下文继续。

## 数据与状态

- **LangGraph State Schema**：`{nl_text, data_source_id, route(单步/多步), plan(dag of sub-tasks), results(per-task outputs), summary, need_confirm_items, error}`
- **子任务**：`{id, type(sql_query/single_step), params, dependencies}`
- **中间结果**：`{columns, row_count, aggregates, error?}`

## 权限与合规

- 查询用户发起（Phase 9 前无鉴权）；执行复用 Phase 5 的只读连接 + 安全校验。
- LLM 摘要治理与 Phase 5 一致：仅聚合结果发 LLM，行级不发。

## 发布与运营

- **迁移**：无。
- **功能开关**：`MULTI_STEP_ENABLED`（默认 true）。
- **运行时依赖**：Phase 3 图谱查询、Phase 5 单步管道、langgraph。
- **监控/告警**：V1 仅日志（路由命中率、DAG 执行成功率）。

## 实现决策

- **模块边界**：`src/agents/`（graph.py + state.py + plan_generator.py）、`src/pipeline/multi_step.py`（DAG 执行器 + 摘要）。
- **接口契约**：
  - 路由：`classify_query(nl_text, data_source_id) → {route, reason}`
  - 计划生成：`generate_plan(nl_text, matched_fields, join_paths) → list[SubTask]`
  - DAG 执行器：`execute_dag(sub_tasks, data_source_id) → {results, errors}`
- **中间结果传递**：`{columns, row_count, aggregates}` 结构化对象；不传原始行。
- **DAG 环检测**：拓扑排序 `Kahn/Tarjan`；无法排序 → 拒执行。
- **依赖**：`langgraph`（已声明）、Phase 3 `shortest_join_path`、Phase 5 `run_single_step`。

## 测试决策

- **测外部行为**：路由判定（单步/多步）、计划生成（DAG 结构）、DAG 执行（成功+失败路径）、LLM 摘要。
- **Mock**：LLM caller、Phase 3 `shortest_join_path`、Phase 5 `run_single_step`、目标库 `query_executor`。
- **手工验收**：「对比本月和上月的销售额」→ 端到端多步拆解+执行+对比摘要。

## 验收标准

- Given 「查昨天的订单总数」→ 路由判定单步 → 由 Phase 5 执行返回。
- Given 「对比本月和上月的销售额」→ 路由命中多步信号 → 拆为两个子查询 DAG → 分别执行 → 合并对比摘要。
- Given 「包含客户名的已完成订单」→ 识别多表+JOIN 路径 → 计划含 JOIN 子查询。
- Given DAG 某子查询失败 → 不阻断其他分支 → 成功结果展示 + 失败标注。
- Given 计划有环 → 拒执行 + 告警。
- Given LLM 摘要仅对聚合子结果做包装，行级结果不摘要。

## 开放问题

1. MULTI_STEP_PATTERNS 覆盖不全（P2）—— V1 用预设 pattern，联调时迭代。
2. DAG 中间结果传递格式的具体字段（V1 `{columns, row_count, aggregates}` 暂定，实现期可能调整）。
3. LLM 调用上限跨 Phase 5/6 共享池的默认值（沿用 Phase 5 的 5，是否够多步场景？）。

## 补充说明

- **设计基线**：§三 多 Agent 协作、dev plan Phase 6
- **Phase 3/5 现实**：PR #22（图谱）+ PR #36（单步管道）已实现
- **预拆 issue**：A 状态图+路由、B 计划生成、C DAG 执行器+摘要。A → B → C
