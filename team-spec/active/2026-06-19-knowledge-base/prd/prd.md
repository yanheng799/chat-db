# 知识库构建（Phase 3）— 字段语义向量库 + 知识图谱

## 问题陈述

Phase 1/2 已把目标库的结构元数据与「带来源标注的语义描述 / 推断外键」存进应用 PostgreSQL。但下游查询 Agent 无法高效利用它们：语义匹配需要**向量近邻检索**（把用户口语映射到字段），多步查询需要**图最短路径**发现 JOIN 关系，而关系库既做不了向量近邻、也做不了图遍历。需要一个把元数据「物化」成**可检索 + 可 JOIN 推理**的知识层（Milvus 向量库 + Neo4j 图谱），并在元数据学习完成后自动刷新。

## 目标

- 学习完成后，激活数据源下每个已覆盖字段（`semantic_description IS NOT NULL`）在 Milvus `field_descriptions` 各有一条向量，支持近邻检索。
- 该源的表/字段/外键/推断关系建成 Neo4j 图谱，支持最短 JOIN 路径与关联表查找。
- 知识库随学习自动刷新：图谱按源全量重建、向量按列增量 upsert。
- 向量构建失败不阻断学习流水线（嵌入服务抖动可恢复）。
- 按数据源隔离，激活切换不擦旧源、查询按激活源过滤。

## 非目标

- **3.4 热词词典**、**3.5 值映射中心** —— 与 Phase 4（查询值标准化：枚举/区域/简称）职责重叠，拆到 Phase 3.b 或并入 Phase 4。
- **`query_samples` 向量集合** —— 依赖查询历史（Phase 5+ 运行期才有）。
- **`SAME_MEANING` 边** —— V1 无自动来源（跨表同义需 LLM/人工）。
- **`JOINS_WITH{frequency}` 边与 JOIN 频次排序** —— 依赖查询历史统计。
- 管理端可视化 UI（Phase 10）；本规格只做后端能力 + 必要只读查询。
- 语义匹配 / SQL 生成 / 多步编排（Phase 5/6）。

## 用户与场景

1. 作为**下游 Agent（Phase 5 语义匹配）**，我希望用字段语义向量近邻检索，把用户口语映射到字段，以便无需人工即可理解查询意图。
2. 作为**下游 Agent（Phase 6 计划生成）**，我希望查最短 JOIN 路径与关联表，以便规划多步查询。
3. 作为**管理员**，我希望在管理端查看表关系图谱（显式 + 推断外键），以便可视化确认（V1 提供查询能力，UI 在 Phase 10）。
4. 作为**系统**，我希望在元数据学习完成后自动把知识库刷新到最新，无需人工搬运。
5. 作为**系统**，我希望嵌入服务抖动时不拖垮学习流水线，下次自动补齐。

## 当前状态

- **Phase 2 已落地（[PR #17](https://github.com/yanheng799/chat-db/pull/17) merged）**：`MetadataColumn`/`MetadataTable` 含 `semantic_description`/`description_source`/`description_confidence`；新表 `metadata_inferred_fks`（推断外键，带 `overlap_rate`/`name_similarity`/`confidence`/`source`）。
- **Phase 1**：`metadata_tables`/`metadata_columns`/`metadata_foreign_keys`/`metadata_indexes`。
- `run_learning`（`learning/orchestrator.py`）在「首次提取后 auto」+「手动」触发（`api/datasources.py`），末尾含 FK 推断步骤（失败抑制）。
- **缺口**：`src/knowledge/` 仅空 `__init__.py`，无任何 Milvus/Neo4j/嵌入客户端代码；仓库无 docker-compose，Milvus/Neo4j/嵌入服务（`:8001`）均为仓库外依赖；`pymilvus>=2.6`/`neo4j` 已声明于 `pyproject.toml`；`config.settings` 已有 `embedding_*`/`milvus_*`/`neo4j_*` 配置项；测试环境当前仅验证 PG。

## 方案描述

**主路径**：元数据学习完成 → 触发知识库刷新（作为 `run_learning` 末尾的独立、失败抑制步骤）：
1. **图谱全量重建（Neo4j）**：按激活 `data_source_id` 先删该源节点/边，再从应用库读取元数据 + 学习结果建图。
2. **向量增量 upsert（Milvus）**：对 `semantic_description IS NOT NULL` 且「描述文本相比已嵌入版本有变化」的列，嵌入 `"{表}.{列}：{semantic_description}"` 写入 `field_descriptions`（键 `column_id`）；未变列不重嵌入。

**下游消费**：向量近邻检索（Phase 5）、最短 JOIN 路径 + 关联表（Phase 6）、图谱只读查询（管理端）。

**变体/失败**：嵌入服务不可用 → 向量 upsert 失败被抑制 + 记日志，图谱照常建成，学习流水线状态不变，失败列下次重跑补齐。激活切换 → 新源构建（不擦旧源），查询按激活源过滤。

## 范围

### 范围内

- 3.1 向量库 Milvus `field_descriptions`（嵌入、增量 upsert、近邻检索）。
- 3.2 图谱构建 Neo4j（Table/Column 节点 + CONTAINS/REFERENCES/INFERRED_REF 边，按源全量重建）。
- 3.3 图谱查询（最短 JOIN 路径 + 关联表查找）。
- 知识库刷新接入 `run_learning`（末尾 suppress 步骤）。
- 数据源删除时清理 Milvus/Neo4j 该源的孤儿数据。

### 范围外

- 3.4 热词词典、3.5 值映射中心（→ Phase 3.b / Phase 4）。
- `query_samples`、`SAME_MEANING`、`JOINS_WITH{frequency}`、JOIN 频次排序。
- 管理端 UI（Phase 10）。
- Phase 5/6 消费侧逻辑。

## 功能需求

1. 系统必须在 `run_learning` 完成后自动刷新激活数据源的知识库（图谱全量重建 + 向量增量 upsert），且该步骤失败不改变学习日志状态。
2. 系统必须把激活源下 `semantic_description IS NOT NULL` 的列嵌入 Milvus `field_descriptions`（文本=`表.列：描述`，payload 含 `column_id`/`data_source_id`/`table`/`column`/`description_source`/`description_confidence`）。
3. 系统必须按 `column_id` 做向量增量：仅嵌入「`semantic_description` 文本相比已嵌入版本有变化」的列；未变列不重嵌入。
4. 系统必须为激活源建 Neo4j 图：Table/Column 节点 + `CONTAINS` + `REFERENCES{confidence}`（显式外键）+ `INFERRED_REF{confidence}`（推断外键，全部入图），节点/边带 `data_source_id`。
5. 系统必须提供图谱查询：两表间最短 JOIN 路径、某表的关联表，均按激活源过滤、不跨源串联。
6. 系统必须提供向量近邻检索（按激活源过滤）。
7. 系统必须在数据源被删除时清理 Milvus/Neo4j 中该源的节点/边/向量记录。
8. 嵌入/向量失败必须被抑制 + 记日志，不阻断图谱构建与学习流水线。

## 业务规则

- **嵌入文本**：`"{表名}.{列名}：{semantic_description}"`（描述为主、表列上下文消歧）；表有语义描述时可前置。
- **入库范围**：只索引 `semantic_description IS NOT NULL` 的列；未覆盖列不入向量库（与 Phase 2 覆盖率口径一致）。
- **图谱边**：`CONTAINS`/`REFERENCES{confidence}`/`INFERRED_REF{confidence}` 全部入图，`confidence` 作边属性；构建期不按置信度裁剪，由查询侧过滤。不建 `SAME_MEANING`/`JOINS_WITH`。
- **同步策略**：图谱按激活源**全量重建**（先删后建）；向量**增量 upsert**（按 `column_id`、按描述文本变化判定）。
- **隔离**：节点/向量记录均带 `data_source_id`；激活切换**不擦旧源**，只为新激活源构建；查询按当前激活源过滤。
- **集成点**：知识库刷新作为 `run_learning` 末尾**独立 suppress 步骤**，不进入学习状态判定逻辑。
- **失败语义**：向量 upsert 失败抑制 + 记日志 + 下次学习重跑重试（幂等）；图谱构建独立、不受向量失败影响。
- **删除语义**：数据源删除 → 清理该源在 Milvus/Neo4j 的全部记录（应用库 CASCADE 不级联到外部存储）。

## 边界情况与错误状态

- 未覆盖列（`semantic_description` 为空）→ 不入向量库，向量检索不到。
- 低置信度（如 0.65）推断外键 → 仍在图中（构建期不裁剪），查询侧按 `confidence` 过滤。
- 跨数据源的最短路径查询 → 不串联两源节点（按 `data_source_id` 隔离）。
- 嵌入服务不可用 → 图谱仍建成；向量 upsert 失败被抑制 + 记日志；学习流水线状态不变；下次重跑补齐失败列。
- 图谱全量重建期间 → 短暂不可用可接受（V1 无蓝绿；重建即覆盖）。
- 激活切换到新数据源 → 新源构建（旧源数据保留）；查询切到新源。
- 数据源被删除 → Milvus/Neo4j 该源记录被清理，无孤儿残留。
- 同一列描述文本未变 → 不重嵌入（避免重复成本）。

## 数据与状态

- **Milvus `field_descriptions`**：`id`=`column_id`；`vector`（1024 维，cosine 度量，HNSW 索引）；payload `{data_source_id, table, column, description_source, description_confidence}`。生命周期：随学习增量 upsert；DS 删除时按 `data_source_id` 清理。
- **Neo4j**：
  - `(:Table {data_source_id, schema, name, row_count})`、`(:Column {data_source_id, table, name, type, is_pk, nullable})`。
  - 边：`(:Table)-[:CONTAINS]->(:Column)`；`(:Column)-[:REFERENCES{confidence}]->(:Column)`（显式）；`(:Column)-[:INFERRED_REF{confidence}]->(:Column)`（推断）。
  - 生命周期：按源全量重建（先删后建）；DS 删除时按源清理。建议索引：`Table(name)`/`Column(name)` + `data_source_id`。
- **应用 PostgreSQL**：schema 不变（Phase 1/2 已就绪）。
- **状态**：知识库无独立状态机；刷新幂等、随学习触发。

## 权限与合规

- **触发权限**：随学习——auto（系统，首次提取后）+ manual（管理员）。知识库无独立写入口（除内部刷新）。
- **可见性**：知识库供下游 Agent 与管理端只读消费；按数据源隔离，查询始终针对激活源。
- **数据治理**：嵌入对象是**派生的 `semantic_description`**（非原始业务数据）、用**本地嵌入模型**（`:8001`，无外发）——无 PII/外发风险，与 Phase 2 L2「不下发原始行」约束无关。
- **审计**：知识库刷新日志复用学习日志体系（失败记日志）；独立审计延 Phase 11。

## 发布与运营

- **迁移**：应用库无 schema 变更。Milvus collection 与 Neo4j 图谱在首次刷新时由代码创建（运行时建 schema/索引）。
- **功能开关**：无；知识库刷新为学习后的自动行为。
- **运行时依赖前置（重要）**：Milvus、Neo4j、嵌入服务（`:8001` 本地 `bge-large-zh-v1.5`）需在部署/测试环境就绪；仓库无 docker-compose 编排，需由部署/Ops 或开发者启动。客户端（pymilvus、neo4j-driver、嵌入 HTTP）从零实现（依赖已声明于 `pyproject.toml`）。
- **监控/告警**：V1 仅记日志；自动监控/告警与 partial/failed 运营处置延 Phase 11。
- **回滚**：禁用「知识库刷新」步骤即可——学习流水线其余部分（L0/L1/L2/FK 推断）照跑，下游降级为无可检索知识层。

## 实现决策

- **模块边界（ownership）**：`src/knowledge/`（向量库客户端、图谱客户端、图谱查询、嵌入客户端）；接入点在 `learning/orchestrator.py`（`run_learning` 末尾独立 suppress 步骤）；配置在 `config.settings`（`embedding_*`/`milvus_*`/`neo4j_*` 已就绪）。不引入图谱层对目标业务库的依赖（只读应用库）。
- **接口契约**：
  - 知识库刷新 = `run_learning` 末尾独立 `suppress(Exception)` 步骤，**不参与**学习状态判定。
  - 向量增量判定 = **方案 A**：查 Milvus 已存 payload 与当前应用库 `semantic_description` 比对，按 `column_id` 只 upsert 文本变化者（自包含，无应用库 schema 变更、无新迁移）。
  - 图谱全量重建 = 按源「先删后建」。
- **已确认 schema 决策**：Milvus `field_descriptions`（1024 维、**cosine**、HNSW）；Neo4j 节点/边带 `data_source_id`；V1 只建 `CONTAINS`/`REFERENCES`/`INFERRED_REF` 三种边。
- **依赖**：`pymilvus>=2.6`、`neo4j`（已声明）；嵌入服务 HTTP（无新依赖）。

## 测试决策

- **测外部行为，不测实现细节**：通过知识库客户端/查询的公共入口验证（向量入库与近邻、图谱节点/边、最短路径、DS 删除清理、失败非致命、按源隔离）。
- **Mock 边界**：嵌入服务（HTTP）、Milvus/Neo4j 客户端（单测可用 fake/in-memory 替身）。
- **基础设施门槛**：端到端集成测试需 Milvus + Neo4j + 嵌入服务在测试环境就绪；当前测试环境仅 PG。建议——纯逻辑（嵌入文本构造、增量比对、Cypher/检索查询构造、源隔离过滤）走单测；集成测试标 **infra-gated**（有基础设施时跑）或后置。
- **现有测试模式**：参考 `learning` 包行为测试（公共入口、mock 外部依赖、真实 async session）。
- **手工验收**：对一个含已覆盖字段与推断外键的数据源跑一次学习，检查 Milvus `field_descriptions` 有对应向量、Neo4j 有 Table/Column 节点与三种边、`orders↔customers` 最短路径返回经由 `customer_id` 的路径。

## 验收标准

- Given 激活源有已覆盖字段，When 学习完成，Then Milvus `field_descriptions` 每个该类字段一条向量（文本=`表.列：描述`，payload 含 `column_id`/`data_source_id`/`description_source`/`description_confidence`）。
- Given 向量近邻检索「订单的状态」，When 查询，Then 命中 `orders.status`（而非 `customers.status`），证明表列上下文消歧生效。
- Given 激活源有表/字段/外键/推断外键，When 学习完成，Then Neo4j 含该源全部 Table/Column 节点 + `CONTAINS`/`REFERENCES{confidence}`/`INFERRED_REF{confidence}` 边。
- Given `orders` 与 `customers` 经由 `customer_id`（显式或推断外键），When 查最短 JOIN 路径，Then 返回该路径。
- Given 已嵌入的列描述未变，When 重跑学习，Then 该列不重嵌入（向量无重复、无多余嵌入调用）。
- Given 嵌入服务不可用，When 学习完成，Then 图谱照常建成、向量 upsert 失败被抑制+记日志、学习日志状态不受影响。
- Given 激活切换到新数据源，When 触发，Then 新源构建且旧源图谱/向量保留；查询按新激活源过滤。
- Given 跨源的两表，When 查最短路径，Then 不串联两源节点（按 `data_source_id` 隔离）。
- Given 一个数据源被删除，When 删除完成，Then Milvus/Neo4j 中该源的节点/边/向量记录全部清理、无孤儿。

## 开放问题

1. **DS 删除清理时机**（owner: @yanheng）：删除时即时清理 vs 接受孤儿（查询按激活源不命中）。PRD 默认：**即时清理**。不解决：删除源后外部存储留垃圾、长期膨胀。
2. **增量判定方案 A vs B**（owner: 实现者）：A=查 Milvus 比对（无迁移，PRD 默认）/ B=在 `metadata_columns` 加 `embed_hash` 列（需迁移）。不解决：实现期再定，可能引入迁移。
3. **运行时依赖可用性**（owner: @yanheng / Ops）：Milvus/Neo4j/嵌入服务(`:8001`)在部署与测试环境就绪。不解决：Phase 3 无法端到端验证与上线。
4. **Phase 5 ↔ 3.4 依赖**（owner: @yanheng）：Phase 5 语义匹配 layer 1 需 3.4 热词词典；需确保 3.4 早于 Phase 5 落地。

## 补充说明

- **设计基线**：`docs/自然语言数据库查询需求设计.md` §九 知识图谱系统、§二 2.2 数据存储职责边界；`docs/development-plan.md` Phase 3（3.1–3.5）。
- **规格来源**：`team-spec/active/2026-06-19-knowledge-base/spec/refine.md`（5 轮细化）+ `spec/reviews.md`（Status: ready，P1 基础设施 + 5 项 P2）。
- **Phase 2 产出**：[PR #17](https://github.com/yanheng799/chat-db/pull/17)（`semantic_description` 系列 + `metadata_inferred_fks`）。
- **后续工程 issue 预拆（供 `team-prd-to-issues`）**：A 向量库（Milvus `field_descriptions` + 嵌入客户端 + 增量 upsert + 近邻检索）、B 图谱构建（Neo4j 客户端 + 建图 + 按源全量重建）、C 图谱查询（最短路径 + 关联表）、D 知识库刷新接入 `run_learning`（末尾 suppress 步骤）+ DS 删除清理。落地顺序建议：A/B 可并行 → C 依赖 B → D 依赖 A/B。
