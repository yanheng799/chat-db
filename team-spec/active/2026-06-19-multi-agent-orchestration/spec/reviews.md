# 规格评审 — 多 Agent 编排 LangGraph（Phase 6）

- **slug**：`2026-06-19-multi-agent-orchestration`
- **评审日期**：2026-06-19
- **评审对象**：`spec/refine.md`（4 轮细化完成版）
- **评审依据**：设计文档 §三 多 Agent 协作流程、开发计划 Phase 6（6.1–6.6）、Phase 3/5 已实现（PR #22/#36）、`langgraph` 已在 pyproject
- **Status**：`ready`（无 P0、P1 LLM 管控可跟踪）

## 结论

4 轮细化覆盖范围切片、路由判定、DAG 故障恢复、图谱集成与摘要治理，验收口径可观察。无 P0、无阻塞 PRD 固化的 P1。最大风险来自「性能与成本」维度——LangGraph 编排增加 LLM 调用（计划生成+摘要），叠加 Phase 5 单步的 LLM 消耗，需全局上限管控。

## 阻塞项

无。

## 风险清单

| 等级 | 风险 | 触发条件 | 影响 | 证据/缺口 | 建议动作 | Owner | 截止点 |
|---|---|---|---|---|---|---|---|
| P1 | 多步 LLM 调用叠加单步消耗 | 用户多步查询 | 延迟与成本翻倍（计划生成+摘要 vs Phase 5 的 2-3 次） | refine 标注了计划生成+摘要两个新增 LLM 调用点 | PRD 沿用 Phase 5 `pipeline_llm_max_calls` 模式，多步查询单独设上限或共享池 | 实现者 | 开发时 |
| P2 | MULTI_STEP_PATTERNS 正则覆盖不全 | 用户复杂句式 | 漏判→该拆的没拆（单步执行失败或结果不准）；误判→不该拆的拆了（增加延迟） | dev 计划给了 3 组 pattern，refine 沿用；未测试实际覆盖 | V1 用预设 pattern；Phase 6/7 联调时收集实际命中率、迭代补充 | 实现者 | Phase 6 联调后 |
| P2 | DAG 环检测缺失 | 计划生成输出有环 DAG | 执行器死循环/无限等待 | refine 提到「做环检测，发现环→拒绝」但未定义检测时机与算法 | PRD 显式标注：执行前对计划 DAG 做拓扑排序检测，无法拓扑→拒执行+告警 | 实现者 | 开发时 |
| P2 | 子任务间中间结果传递格式 | 多步 DAG 中有依赖的子任务 | 传递全量行→浪费内存+治理风险；传递太少→后一步无上下文 | refine 只提了「传聚合统计值」，未定义结构化 schema | PRD 补：子结果传递为 `{columns, row_count, aggregates}` 结构化摘要 | 实现者 | 开发时 |
| P3 | `langgraph` 库版本兼容 | LangGraph 安装后 | API 差异导致编译/运行时错误 | `langgraph` 已在 pyproject 但未锁定版本 | 实现期锁版本或 `>=min` | 实现者 | 开发时 |

## 需要补充的问题

无（均为 P2/P3，不阻塞 PRD，可在 PRD 或开发时补入）。

## 建议改写（供 PRD 时补入，不改 refine.md）

- **LLM 调用上限**：补多步查询的 `pipeline_llm_max_calls` 与 Phase 5 单步共享池的规则。
- **DAG 环检测**：补「执行前拓扑排序→无法拓扑即拒绝」。
- **中间结果传递格式**：补 `{columns, row_count, aggregates}` schema。

## Change Log

- 2026-06-19：首次评审。4 轮细化决议完整、复用 Phase 3/5 已实现模块。无 P0、P1 仅 LLM 管控；3 项 P2（路由覆盖、环检测、中间结果）+ 1 项 P3。结论 `ready`。
