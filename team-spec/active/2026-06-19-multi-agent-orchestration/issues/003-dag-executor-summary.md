# 实现 DAG 执行器——按拓扑序执行子查询并传递结果、合并 LLM 摘要

## Parent

PRD：`team-spec/active/2026-06-19-multi-agent-orchestration/prd/prd.md`（6.6 多步串联，issue C）

## What to build

实现多步 DAG 执行器：对计划生成 Agent 产出的子任务 DAG 做拓扑排序（Kahn/Tarjan）→ 按序执行子查询（每个子任务复用 Phase 5 `run_single_step` 或独立 SQL 生成+执行）→ 子任务间传递结构化中间结果（`{columns, row_count, aggregates}`，不传原始行）→ best-effort 故障恢复（子任务失败→标记节点 failed、跳过其后继，不阻断不相关分支）→ 最终合并结果 + LLM 自然语言摘要（仅对聚合子结果做包装；行级不摘要）。执行前做 DAG 环检测→有环拒执行+告警。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given 两个不相关的子任务（本月的销售额 + 上月的销售额），When 执行 DAG，Then 两者并行执行、结果合并。
- [ ] Given 子任务 A→B 有依赖（A 的结果传给 B），When 执行，Then A 先执行、结果传给 B 后再执行 B。
- [ ] Given DAG 中某子任务失败，When 执行，Then 不阻断不相关分支、成功结果正常返回、失败任务标注原因。
- [ ] Given 计划 DAG 有环，When 拓扑排序，Then 检测到环、拒执行+告警。
- [ ] Given 聚合子结果，When LLM 摘要，Then 生成自然语言对比/汇总描述；行级结果不传入摘要。
- [ ] 子任务间中间结果传递格式为 `{columns, row_count, aggregates}`，不传原始行。

## Blocked by

- #1（状态图）、#2（计划生成）

## Notes

- DAG 执行器在 `src/pipeline/multi_step.py`。
- LLM 摘要复用 `llm/client.py`；治理与 Phase 5 一致（仅聚合发 LLM）。
- 测试 mock Phase 5 子执行 + mock LLM 摘要。

## Publish Status

- Status: created
- Updated At: 2026-06-19T07:30:06Z
- GitHub Number: 39
- GitHub URL: https://github.com/yanheng799/chat-db/issues/39
