# 规格评审报告

> slug: `2026-06-05-db-connection-metadata`
> 评审日期：2026-06-05（三次评审——复核表级同步变更）
> 评审输入：`spec/refine.md` v3 + 前次评审报告
> 评审人：Claude Code

## 结论

表级同步变更干净、一致，未引入新的阻塞风险或 P1。新增的 `scope` 字段和 `table_scope` API 参数设计合理，向后兼容。规格可以进入 PRD 固化。

**Status: ready**

## 阻塞项

无。

## 变更复核

| 变更点 | 评估 | 结论 |
|--------|------|------|
| `metadata_sync_logs.scope` JSONB 字段 | null 表示全量，数组表示表级范围。定时同步自动 null。格式一致。 | ✅ 无风险 |
| `POST /api/datasources/{id}/sync` 增加 `table_scope` body | 可选参数，不传 = 全量（向后兼容）。格式 `[{schema, table}]` 与 PG/MySQL 适配表一致。 | ✅ 无风险 |
| 同步逻辑新增表级规则 | 增量检查语义明确。表不存在 → `table_removed`。覆盖字段/索引/外键。 | ✅ 无风险 |
| 并发同步风险是否加剧 | 表级同步与全量同步并发场景与之前评审的 P2 一致，无新增维度 | ✅ 无新增风险 |

## 风险清单

（与二次评审一致，新增 1 条 P3）

| 等级 | 风险 | 触发条件 | 影响 | 证据/缺口 | 建议动作 | Owner | 截止点 |
|------|------|----------|------|-----------|----------|-------|--------|
| P2 | 并发同步无防护 | 定时/手动/表级同步重叠 | 数据不一致 | 行为规则未提及并发 | PRD：同一 data_source 仅允许一个 running sync_log，冲突返回 409 | PRD | PRD 中 |
| P2 | 级联删除未明确 | 删除 data_source | FK 约束未设 CASCADE 则删除失败 | 数据模型未指定 ON DELETE | PRD：所有 FK 设 ON DELETE CASCADE | PRD | PRD 中 |
| P3 | "全量快照覆盖"表述歧义 | 实现者误解 | DELETE+INSERT 而非 diff | 功能范围 vs 行为规则措辞 | PRD：使用"差异更新" | PRD | PRD 中 |
| P3 | asyncmy 兼容性 | 特定 MySQL 版本 | 连接失败 | 社区较小 | 实现时测试兼容性 | 实现 | 开发中 |
| P3 | 表级同步：新表场景未显式说明 | `table_scope` 指定的表在目标库存在但元数据仓库中不存在 | 实现者可能忽略 `table_added` 路径 | 同步逻辑仅显式提及 `table_removed` | PRD：明确表级同步也检测 `table_added`（指定表在目标库存在但元数据中不存在） | PRD | PRD 中 |

## 需要补充的问题

无。

## Questions For User

不适用（Status: ready）。

## Required Refinement

不适用（Status: ready）。

## PRD 注意事项

以下内容应在 PRD 中直接补入，无需回到 refine：

1. **并发同步防护**：同一 data_source 同一时刻仅允许一个 running 的 sync_log，冲突返回 HTTP 409
2. **级联删除**：所有 FK 约束设 ON DELETE CASCADE
3. **措辞修正**：将"全量快照覆盖"改为"差异更新"
4. **验收标准**：明确 Phase 1 检查点的可测试验收条件
5. **表级同步 table_added**：明确表级同步时，指定表在目标库存在但元数据中不存在，应记录 `table_added` 并插入元数据
