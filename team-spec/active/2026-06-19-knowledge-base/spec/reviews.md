# 规格评审 — 知识库构建（Phase 3）

- **slug**：`2026-06-19-knowledge-base`
- **评审日期**：2026-06-19
- **评审对象**：`spec/refine.md`（5 轮细化完成版）
- **评审依据**：设计文档 §九、开发计划 Phase 3、`src/config/settings.py`、`pyproject.toml`、`src/knowledge/`（空）、仓库 infra（无 docker-compose）、`test/`（仅连 PG）
- **Status**：`ready`（无 P0、无阻塞 PRD 固化的 P1；P1 为实现/验证前置的基础设施依赖，可在 PRD/issue 阶段跟踪）

## 结论

规格可进入 PRD 固化：5 轮细化已覆盖范围切片、触发/同步、图谱边范围、向量化文本、失败处理，验收口径可观察、可测试。无 P0，无阻塞 PRD 固化的 P1。最大风险来自**「技术依赖 + 测试与验收」**维度——Milvus / Neo4j / 嵌入服务（`:8001`）均为仓库外外部依赖（无 docker-compose 编排、`src/knowledge/` 为空、客户端需从零实现），且测试环境目前只验证 PG，Phase 3 端到端验证依赖这些基础设施就绪。

## 阻塞项

无（不阻塞 PRD 固化）。P1 风险见下，属开发/验证前置，非 PRD 前置。

## 风险清单

| 等级 | 风险 | 触发条件 | 影响 | 证据/缺口 | 建议动作 | Owner | 截止点 |
|---|---|---|---|---|---|---|---|
| P1 | 基础设施未编排 + 客户端从零 + 测试环境缺位 | Phase 3 开发/验证 | 无法端到端验证；开发期才发现缺服务则延期 | 仓库无 docker-compose；`src/knowledge/` 仅空 `__init__.py`；`test/` 无 milvus/neo4j（仅连 PG）；`pymilvus>=2.6`/`neo4j` 已在 pyproject 但无客户端代码 | issue 阶段：搭建/确认 Milvus+Neo4j+嵌入服务；实现 pymilvus/neo4j/嵌入客户端；为端到端测试准备基础设施或明确 mock 边界（向量/图谱可单测纯函数 + 集成测试可选） | @yanheng | Phase 3 开发前 |
| P2 | 数据源删除 → Milvus/Neo4j 孤儿数据 | 管理员删除数据源 | 删除后图谱节点/向量残留 | 应用库 CASCADE 删元数据，但 Milvus/Neo4j 独立存储不级联；refine 未提及 | PRD 补「DS 删除时清理该源图谱节点/边 + 向量记录」，或显式接受孤儿（查询按激活源过滤不命中）并注明 | @yanheng | 进 PRD 前 |
| P2 | 增量 upsert「变化」判定机制未定 | 每次学习重跑 | 影响正确性与成本 | 需对比「当前描述」与「已嵌入」；方案未选 | PRD/issue 选定：A=查 Milvus 比对（自包含、无迁移，推荐）/ B=在 `metadata_columns` 加 `embed_hash`（需迁移） | 实现者 | 拆 issue 时 |
| P2 | Milvus 检索度量（metric）未指定 | 向量检索 | 影响召回正确性 | bge 嵌入通常用 cosine；refine 未写度量 | PRD 注明 collection 用 cosine + 建索引（HNSW/IVF） | 实现者 | 拆 issue 时 |
| P2 | Phase 5 依赖延期的 3.4 热词词典 | Phase 5 语义匹配 layer 1 | Phase 5 layer 1 无词典可用 | 本规格延期 3.4（→ Phase 3.b/Phase 4），但 Phase 5 需要它 | Phase 5 规格显式标注「依赖 3.4 已落地」；确保 3.4 早于 Phase 5 | @yanheng | Phase 5 规格时 |
| P2 | 构建与 `run_learning` 的集成点未钉死 | 实现期 | 影响事务/会话边界与 suppress 包裹 | 「不阻断学习流水线」已定，但具体挂载点（末尾 suppress 步骤 vs 完成后钩子）未选 | PRD 注明：作为 `run_learning` 末尾独立 suppress 步骤（或学习完成后单独调用），不进入状态判定逻辑 | 实现者 | 拆 issue 时 |
| P3 | Neo4j 索引 / Milvus 分区 / 并发 | 规模/性能 | shortestPath 无索引会慢；多源可分区 | 未提 | 实现期加 `Table(name)`+`data_source_id` 索引、按源分区；并发由 Phase 2 学习互斥覆盖 | 实现者 | 开发时 |

## 需要补充的问题

1. 数据源删除时，Milvus/Neo4j 是否即时清理（P2）？还是接受孤儿（查询按激活源过滤不命中）？
2. 增量 upsert 变化判定用方案 A（查 Milvus 比对）还是 B（加 `embed_hash` 列、需迁移）？

（均为 P2，不阻塞 PRD 固化；可在 `team-spec-to-prd` 直接补入或留给 issue 阶段。）

## 建议改写（供 PRD 固化时补入，不改 refine.md）

无需改写 refine.md 现有决议。建议 PRD 固化时补三处：
- **数据与状态**：补「数据源删除 → 清理该源图谱节点/边 + 向量记录」（P2 问题 1 的默认动作：即时清理）。
- **实现决策**：补「增量变化判定 = 方案 A（查 Milvus 比对，无 schema 变更）」「Milvus collection metric = cosine + HNSW 索引」「构建作为 `run_learning` 末尾独立 suppress 步骤」。
- **发布与运营**：补「运行时依赖前置：Milvus / Neo4j / 嵌入服务（`:8001`）需在部署/测试环境就绪；客户端从零实现；`pymilvus>=2.6`/`neo4j` 依赖已声明」。

## Change Log

- 2026-06-19：首次评审。对照代码与 infra 核验：确认 pymilvus/neo4j 已声明、`src/knowledge/` 空、无 docker-compose、测试仅连 PG。无 P0；P1=基础设施+测试环境前置；5 项 P2（DS 删除清理、增量判定、metric、Phase5↔3.4 依赖、集成点）+ 1 项 P3。结论 `ready`，可进 PRD。
