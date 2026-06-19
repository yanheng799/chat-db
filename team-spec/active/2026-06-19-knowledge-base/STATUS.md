# STATUS

状态：implemented（#18–#21 四 issue 已实现并验证，均 ready for PR，未提交）

- 2026-06-19：`team-spec-refine` 5 轮，确认：
  - 范围 = 核心三件套（向量库 `field_descriptions` + 图谱构建 + 图谱查询）；3.4 热词词典 / 3.5 值映射中心延期；`query_samples` 后置。
  - 触发/同步 = 链在 `run_learning` 之后 + 图谱按激活源全量重建 + 向量按 `column_id` 增量 upsert + 按 `data_source_id` 隔离不擦旧 + 无蓝绿。
  - 图谱 V1 边 = CONTAINS/REFERENCES/INFERRED_REF 全入（confidence 作属性）；SAME_MEANING / JOINS_WITH 延期；3.3 只做最短路径 + 关联表，频次排序延期。
  - 向量化文本 = `表.列：描述`，只索引 `semantic_description IS NOT NULL` 的列，按描述文本变化增量。
  - 嵌入/失败 = 两库独立、向量失败抑制+日志+下次重试、不阻断；本地模型无外发。
- 延期项：`SAME_MEANING` 来源（人工/LLM）、`JOINS_WITH` 频次（待查询历史）、`query_samples`（待查询历史）、3.4 / 3.5（归 Phase 3.b 或 Phase 4）。
- 下一步：`team-spec-review` 复查 `spec/refine.md` 是否 ready；通过后 `team-spec-to-prd`。
- 2026-06-19（评审）：`team-spec-review` 对照代码/infra 核验——pymilvus/neo4j 已声明、`src/knowledge/` 空、无 docker-compose、测试仅连 PG。无 P0；P1=基础设施(Milvus/Neo4j/嵌入)+测试环境前置；5 项 P2（DS 删除清理、增量判定机制、Milvus metric、Phase5↔3.4 依赖、构建集成点）。结论 `ready`，报告见 `spec/reviews.md`。
- 下一步：`team-spec-to-prd` 固化 PRD（建议补：DS 删除清理、增量判定方案 A、cosine metric、构建为 run_learning 末尾 suppress 步骤、运行时依赖前置）。
- 2026-06-19（PRD 固化）：基于 `Status: ready` 的 review 生成 `prd/prd.md`（在 main 上）；吸收 review P2（DS 删除清理、增量方案 A、cosine+HNSW、构建为末尾 suppress 步骤、运行时依赖前置）；预拆 A/B/C/D 四 issue。
- 下一步：`team-prd-to-issues` 拆工程 issue（建议顺序 A/B 并行 → C → D）。
- 2026-06-19（拆 issue）：生成 4 个本地 AFK issue 草稿——`issues/001-vector-store-field-descriptions.md`（A）、`002-graph-build-from-metadata.md`（B）、`003-graph-query-join-paths.md`（C，blocked by 002）、`004-knowledge-lifecycle-refresh-and-cleanup.md`（D，blocked by 001+002）。建议实现顺序 001/002 并行 → 003、004。
- 下一步：`team-issue-batch-implement`（按 001/002→003/004 连续实现）或 `team-issue-publish-github`（发布到 GitHub Issues 跟踪）。
- 2026-06-19（发布 issue）：4 个 issue 已发布到 GitHub Issues——[#18](https://github.com/yanheng799/chat-db/issues/18)（001 向量库）、[#19](https://github.com/yanheng799/chat-db/issues/19)（002 图谱构建）、[#20](https://github.com/yanheng799/chat-db/issues/20)（003 图谱查询，依赖 #19）、[#21](https://github.com/yanheng799/chat-db/issues/21)（004 生命周期，依赖 #18+#19）。本地草稿已回写 GitHub 编号/URL。
- 下一步：`team-issue-batch-implement`（按 001/002→003/004；前提 Milvus/Neo4j/嵌入服务 infra 就绪）或先搭基础设施。
