# 规格评审 — 知识库构建（Phase 3）

- **slug**：`2026-06-19-knowledge-base`
- **评审日期**：2026-06-21（第 2 次评审）
- **评审对象**：`spec/refine.md`（7 轮细化，含递归 FK 遍历 + 图谱 UX 归属）
- **评审依据**：`spec/refine.md`、`src/knowledge/`（已实现：`graph_store.py` / `graph_query.py` / `vector_store.py` / `embedding.py` / `lifecycle.py`）、`src/learning/orchestrator.py`、`src/api/datasources.py`、`test/`
- **Status**：`ready`（无 P0，无阻塞 PRD 固化的 P1；两个 P2 为已知风险/遗留项）

## 结论

规格可进入 PRD 固化或直接拆 issue 实现。核心三件套（向量库 + 图谱构建 + 图谱查询）已实现并验证；新增的递归 FK 遍历需求已澄清（Scenario A/B），无歧义。上一次评审的 7 项风险中 5 项已在实现中解决，剩余 2 项 P2 为已知遗留/跟踪项。

## 阻塞项

无。

## 上次评审风险回顾

| 等级 | 风险 | 状态 |
|------|------|------|
| P1 | 基础设施未编排 + 客户端从零 | ✅ 已解决 — `src/knowledge/` 已实现 VectorStore、GraphStore、EmbeddingClient；Milvus/Neo4j/嵌入服务客户端已就绪 |
| P2 | DS 删除 → 孤儿数据 | ✅ 已解决 — `cleanup_knowledge_base()` 已实现，`delete_data_source` 调用 |
| P2 | 增量 upsert 变化判定 | ✅ 已解决 — `compute_upsert_plan()` 用方案 A（查 Milvus 比对） |
| P2 | Milvus metric 未指定 | ✅ 已解决 — Cosine + HNSW 索引已配置 |
| P2 | Phase 5 ↔ 3.4 依赖 | ⏸️ 仍延期，Phase 5 规格时跟踪 |
| P2 | 构建集成点 | ✅ 已解决 — `run_learning` 末尾 `suppress` 步骤调用 `refresh_knowledge_base` |
| P3 | Neo4j 索引 / 分区 / 并发 | ⏸️ 记录即可 |

## 新增风险（递归 FK 遍历 + 图谱 UX 变更）

| 等级 | 风险 | 触发条件 | 影响 | 证据/缺口 | 建议动作 | Owner | 截止点 |
|------|------|----------|------|-----------|----------|-------|--------|
| P2 | 递归遍历在大图上超时 | 数百张表 + 密集 FK 边时 | `connected_subgraph` Cypher 查询可能指数爆炸 | 已设 `_MAX_PATH_DEPTH=6`；schema 通常 <100 表 | 实现时加 query timeout（Neo4j 侧 `transaction_timeout` 或 Python 侧 `asyncio.wait_for`）；单测用 50+ 表合成图验证 | 实现者 | 实现时 |
| P2 | `connected_subgraph` 多表输入不全连通 | 用户/Agent 查询的表没有全部连在同一个子图中 | 返回部分结果或空，需要明确的错误语义 | refine 未定义不全连通时的行为 | 实现时定义：返回 `None`（表示无法全连接）或返回已连通的子图 + 未连通表清单；前端/AI 端据此调整 UI/plan | 实现者 | 实现时 |
| P3 | 前端"选表→展开可达网络"交互未设计 | 实现时 | UX 不佳但非阻塞 | UX 设计缺失 | 实现前确认：下拉选择起始表？点击表中某行展开？折叠面板默认展示"选择一张表查看可达网络"入口 | 实现者 | 前端实现时 |

## 需要补充的问题

1. `connected_subgraph` 多表不全连通时，返回什么？**建议**：返回 `{connected: [[path...]], unconnected: ["table_c", "table_d"]}`，调用方据此判断是否需要 fallback 到逐个两两查询。
2. Cypher 递归查询是否需要加 `transaction_timeout`？推荐默认 5s。

## 建议改写（可进 PRD 时补入）

无重大改写需求。PRD 固化时补入递归遍历的验收口径（已写在 refine.md）和以上两个 P2 的处理方案。

## Change Log

- 2026-06-19：首次评审。对照代码与 infra 核验，7 项风险（1 P1 + 5 P2 + 1 P3），结论 `ready`。
- 2026-06-21：第 2 次评审。回顾上次 7 项：5 项已解决、2 项遗留跟踪。新增递归 FK 遍历 + 图谱 UX 变更评审：2 P2 + 1 P3。结论 `ready`，可进 PRD 或直接拆 issue。
