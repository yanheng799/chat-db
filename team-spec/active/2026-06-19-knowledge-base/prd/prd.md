# 知识库构建（Phase 3）— 字段语义向量库 + 知识图谱

## 问题陈述

Phase 1/2 已把目标库的结构元数据与「带来源标注的语义描述 / 推断外键」存进应用 PostgreSQL。但下游查询 Agent 无法高效利用它们：语义匹配需要**向量近邻检索**（把用户口语映射到字段），多步查询需要**图最短路径**发现 JOIN 关系，而关系库既做不了向量近邻、也做不了图遍历。需要一个把元数据「物化」成**可检索 + 可 JOIN 推理**的知识层（Milvus 向量库 + Neo4j 图谱），并在元数据学习完成后自动刷新。

此外，当前 FK 推断只产出孤立的 1-hop 边（A→B），管理员看不到完整表关联网络；下游 Agent 对多表查询需 N×N 次两两最短路径查询。需要**递归 FK 遍历**，从单表出发连通整个可达子图。

## 目标

- 学习完成后，激活数据源下每个已覆盖字段（`semantic_description IS NOT NULL`）在 Milvus `field_descriptions` 各有一条向量，支持近邻检索。
- 该源的表/字段/外键/推断关系建成 Neo4j 图谱，支持最短 JOIN 路径、关联表查找、**递归可达子图**。
- 知识库随学习自动刷新：图谱按源全量重建、向量按列增量 upsert。
- 向量构建失败不阻断学习流水线（嵌入服务抖动可恢复）。
- 按数据源隔离，激活切换不擦旧源、查询按激活源过滤。
- 管理员可在数据源详情页查看知识图谱（表节点 + 关系），并递归展开某张表的可达网络。

## 非目标

- **3.4 热词词典**、**3.5 值映射中心** —— 与 Phase 4（查询值标准化：枚举/区域/简称）职责重叠，拆到 Phase 3.b 或并入 Phase 4。
- **`query_samples` 向量集合** —— 依赖查询历史（Phase 5+ 运行期才有）。
- **`SAME_MEANING` 边** —— V1 无自动来源（跨表同义需 LLM/人工）。
- **`JOINS_WITH{frequency}` 边与 JOIN 频次排序** —— 依赖查询历史统计。
- 语义匹配 / SQL 生成 / 多步编排（Phase 5/6）。

## 用户与场景

1. 作为**下游 Agent（Phase 5 语义匹配）**，我希望用字段语义向量近邻检索，把用户口语映射到字段。
2. 作为**下游 Agent（Phase 6 计划生成）**，我希望一次性发现连接多张表的完整 JOIN 子图（而非逐对调用最短路径），以便规划多步查询。
3. 作为**管理员**，我希望在数据源详情页查看表关系图谱（显式 + 推断外键），并递归展开某表的可达网络（完整路径链）。
4. 作为**系统**，我希望在元数据学习完成后自动刷新知识库；嵌入服务抖动时不拖垮学习流水线。
5. 作为**系统**，我希望数据源被删除时清理 Milvus/Neo4j 中该源的孤儿数据。

## 当前状态

- **Phase 1/2 已落地**（[PR #17](https://github.com/yanheng799/chat-db/pull/17) merged）：`MetadataColumn`/`MetadataTable` 含 `semantic_description`/`description_source`/`description_confidence`；`metadata_inferred_fks`（推断外键）；`metadata_foreign_keys`/`metadata_indexes`。
- **Phase 3 核心已实现**（issues #18–#21）：`src/knowledge/` 含 VectorStore、GraphStore、GraphQuery（最短路径 + 关联表）、EmbeddingClient、Lifecycle（刷新 + 清理）。`run_learning` 末尾 suppress 步骤调用 `refresh_knowledge_base`。增量 upsert 用方案 A（查 Milvus 比对）。Milvus cosine metric + HNSW 索引已配置。
- **数据源详情页**：已集成知识图谱卡（折叠面板），展示表节点 + 关系（REFERENCES/INFERRED_REF/CONTAINS + 置信度）。
- **学习日志**：`fk_inferred` 字段记录 FK 推断数量。
- **缺失**：递归 FK 遍历（Scenario A 管理端 + Scenario B Agent）。

## 方案描述

**主路径**：元数据学习完成 → 触发知识库刷新（`run_learning` 末尾 suppress 步骤）：
1. **图谱全量重建（Neo4j）**：按激活 `data_source_id` 先删该源节点/边，再建图。
2. **向量增量 upsert（Milvus）**：嵌入 `"{表}.{列}：{semantic_description}"`，按 `column_id` 只 upsert 文本变化者。

**新能力（本次迭代）**：
3. **递归 FK 遍历**：从单表出发沿 REFERENCES/INFERRED_REF 递归遍历（`_MAX_PATH_DEPTH=6`），返回所有可达表及其完整路径链。
   - **Scenario A（管理端）**：`GET /api/admin/graph/reachable/{ds}?from={table}` → 返回 `{from_table, tables: [{name, schema, path: [{from_table, from_column, to_table, to_column, type, confidence}]}]}`。
   - **Scenario B（Agent）**：`graph_query.py` 新增 `connected_subgraph(graph_store, ds, tables[])`，一次性连接多表，替代 `single_step.py` 中 N×N 次两两 `shortest_join_path` 调用。旧方法保留。
4. **管理端交互**：数据源详情页知识图谱卡增加"选择起始表 → 查看可达网络"交互（默认折叠）。

**下游消费**：向量近邻检索（Phase 5）、最短 JOIN 路径 + 关联表 + 递归子图（Phase 6）、图谱只读查询（管理端）。

## 范围

### 范围内

- 3.1 向量库 Milvus `field_descriptions`（嵌入、增量 upsert、近邻检索）。
- 3.2 图谱构建 Neo4j（Table/Column 节点 + CONTAINS/REFERENCES/INFERRED_REF 边，按源全量重建）。
- 3.3 图谱查询（最短 JOIN 路径 + 关联表查找 + **递归可达子图**）。
- 3.3a 管理端图谱查询 API + 前端交互（数据源详情页）。
- 知识库刷新接入 `run_learning`（末尾 suppress 步骤）。
- 数据源删除时清理 Milvus/Neo4j 该源的孤儿数据。

### 范围外

- 3.4 热词词典、3.5 值映射中心（→ Phase 3.b / Phase 4）。
- `query_samples`、`SAME_MEANING`、`JOINS_WITH{frequency}`、JOIN 频次排序。
- 语义匹配 / SQL 生成 / 多步编排（Phase 5/6）。

## 功能需求

1. 系统必须在 `run_learning` 完成后自动刷新激活数据源的知识库。
2. 系统必须把激活源下 `semantic_description IS NOT NULL` 的列嵌入 Milvus（文本=`表.列：描述`，按 `column_id` 增量 upsert）。
3. 系统必须为激活源建 Neo4j 图：Table/Column 节点 + `CONTAINS` + `REFERENCES{confidence}` + `INFERRED_REF{confidence}` 边。
4. 系统必须提供图谱查询：两表间最短 JOIN 路径、某表的关联表、**从某表出发递归遍历所有可达表及路径链**。
5. 系统必须提供向量近邻检索（按激活源过滤）。
6. 系统必须在数据源被删除时清理 Milvus/Neo4j 中该源的记录。
7. 嵌入/向量失败必须被抑制 + 记日志，不阻断图谱构建与学习流水线。
8. 用户可在数据源详情页查看知识图谱（表节点 + 关系列表），并可选择起始表查看递归可达网络。
9. Agent 可通过 `connected_subgraph()` 一次性发现连接多张表的完整 JOIN 子图，替代逐对 `shortest_join_path` 调用（旧方法保留）。

## 业务规则

- **嵌入文本**：`"{表名}.{列名}：{semantic_description}"`。
- **入库范围**：只索引 `semantic_description IS NOT NULL` 的列。
- **图谱边**：CONTAINS/REFERENCES{confidence}/INFERRED_REF{confidence} 全部入图。不建 SAME_MEANING/JOINS_WITH。
- **同步策略**：图谱全量重建（先删后建）；向量增量 upsert（按 `column_id`、按文本变化判定）。
- **隔离**：节点/向量均带 `data_source_id`；激活切换不擦旧源。
- **递归深度**：`_MAX_PATH_DEPTH=6`。Cypher 查询加 5s timeout。
- **多表不全连通时**：`connected_subgraph` 返回 `{connected: [[path...]], unconnected: ["table_c"]}`，调用方据此 fallback。

## 边界情况与错误状态

- 未覆盖列 → 不入向量库。
- 低置信度推断外键 → 仍在图中，查询侧按 confidence 过滤。
- 跨源最短路径/递归遍历 → 不串联两源节点。
- 嵌入服务不可用 → 图谱照建，向量失败抑制+记日志，下次重试。
- 图谱全量重建期间 → 短暂不可用（V1 无蓝绿）。
- 激活切换 → 新源构建，旧源保留。
- 数据源删除 → Milvus/Neo4j 即时清理，无孤儿。
- 递归遍历超时（5s）→ 返回已发现的结果 + 超时标记。
- 多表不全连通 → 返回已连通子图 + 未连通表清单。

## 数据与状态

- **Milvus `field_descriptions`**：`id`=`column_id`；vector（1024 维，cosine，HNSW）；payload `{data_source_id, table, column, description_source, description_confidence}`。
- **Neo4j**：`(:Table {data_source_id, schema, name})`、`(:Column {data_source_id, table, name, type, is_pk, nullable})`。边：`:CONTAINS`、`:REFERENCES{confidence}`、`:INFERRED_REF{confidence}`。
- **应用 PostgreSQL**：schema 不变。`metadata_learning_logs.fk_inferred` 记录 FK 推断计数。

## 权限与合规

- **触发权限**：随学习——auto（首次提取后）+ manual（管理员）。
- **可见性**：知识库供下游 Agent 与管理端只读消费；按数据源隔离。
- **数据治理**：嵌入对象是派生的 `semantic_description`，用本地嵌入模型，无 PII/外发风险。

## 发布与运营

- **迁移**：无应用库 schema 变更。`metadata_learning_logs.fk_inferred` 已添加。
- **运行时依赖**：Milvus、Neo4j、嵌入服务（`:8001`）需在部署/测试环境就绪。
- **监控**：V1 记日志；递归遍历超时记 warning。

## 实现决策

- 增量判定 = 方案 A（查 Milvus 比对，无迁移）。
- 图谱全量重建 = 按源先删后建。
- Milvus = cosine + HNSW（已配置）。
- 递归遍历 = `_MAX_PATH_DEPTH=6` + 5s Cypher timeout。
- `connected_subgraph` 多表不全连通时返回已连通 + 未连通清单。
- `shortest_join_path` 保留，`single_step.py` 优先用 `connected_subgraph`，fallback 到旧逻辑。

## 测试决策

- 纯逻辑（嵌入文本构造、增量比对、Cypher 构造、递归遍历路径输出）走单测。
- 递归遍历用 50+ 表合成图验证性能。
- 集成测试标 infra-gated（需 Milvus + Neo4j + 嵌入服务）。
- 手工验收：学习完成后，`GET /api/admin/graph/reachable/{ds}?from=orders` 返回 orders 可达的所有表及路径链；Agent 调用 `connected_subgraph(ds, ["orders","countries"])` 返回连接路径。

## 验收标准

- Given 激活源有已覆盖字段，When 学习完成，Then Milvus 每个字段一条向量。
- Given 向量近邻检索「订单的状态」，When 查询，Then 命中 `orders.status`（而非 `customers.status`）。
- Given `orders` 与 `customers` 经由 `customer_id` 关联，When 查最短 JOIN 路径，Then 返回该路径。
- Given `orders` → `customers` → `regions` → `countries` 的 FK 链，When 查 `GET /api/admin/graph/reachable/{ds}?from=orders`，Then 返回这 4 张表及完整路径链（深度 ≤ 6）。
- Given `connected_subgraph(ds, ["orders","countries"])`，When 两表连通，Then 返回连接路径；When 不全连通，Then 返回 `{connected: [...], unconnected: [...]}`。
- Given 嵌入服务不可用，When 学习完成，Then 图谱照建、学习状态不受影响。
- Given 数据源被删除，When 删除完成，Then Milvus/Neo4j 该源记录全部清理。

## 开放问题

1. **递归遍历性能**（owner: 实现者）：大图（100+ 表、密集 FK）时性能待验证。缓解：`_MAX_PATH_DEPTH=6` + 5s timeout。在实现时用合成大图验证。
2. **Phase 5 ↔ 3.4 依赖**（owner: @yanheng）：Phase 5 语义匹配 layer 1 需 3.4 热词词典；确保 3.4 早于 Phase 5 落地。

## 补充说明

- **设计基线**：`docs/自然语言数据库查询需求设计.md` §九。
- **规格来源**：`team-spec/active/2026-06-19-knowledge-base/spec/refine.md`（7 轮细化）+ `spec/reviews.md`（2 次评审，Status: ready）。
- **已实现**：向量库 + 图谱构建 + 图谱查询 + 生命周期（issues #18–#21）。递归 FK 遍历为新增需求。
