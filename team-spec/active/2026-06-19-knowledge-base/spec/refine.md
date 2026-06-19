# 知识库构建（Phase 3）— 规格细化

- **slug**：`2026-06-19-knowledge-base`
- **状态**：refining 完成（第 5 轮，核心行为已定，待 `team-spec-review` 复查）
- **基线**：设计文档 §九 知识图谱系统 + §二 2.2 数据存储职责边界；开发计划 Phase 3（3.1–3.5）
- **依赖**：Phase 2 元数据学习（已进 [PR #17](https://github.com/yanheng799/chat-db/pull/17)，产出 `semantic_description` / `description_source` / `description_confidence` / `metadata_inferred_fks`）；Phase 1 元数据（`metadata_tables` / `metadata_columns` / `metadata_foreign_keys` / `metadata_indexes`）
- **关联决策**：待定（图谱与向量库的数据源隔离、重建策略）

## 需求复述

把 Phase 1/2 提取并学习到的元数据「物化」成下游查询 Agent 可消费的**知识层**：字段语义描述向量化进 Milvus 供语义匹配检索；表/字段/外键/推断关系建成 Neo4j 图谱供 JOIN 路径发现与表关系可视化。一句话：把元数据变成「可检索 + 可 JOIN 推理」的知识库。

## 问题与价值

- **痛点**：Phase 2 只在应用 PostgreSQL 里存了语义描述与推断外键，下游无法高效检索（语义匹配要向量近邻）或推理关系（多步 JOIN 要图最短路径）。
- **价值**：向量库让 Phase 5 把用户口语映射到字段；图谱让 Phase 6 多步查询发现 JOIN 路径、让管理端可视化确认表关系。
- **触发**：待确认（见「开放问题 1」）。

## 用户与场景

1. 作为**下游 Agent**（Phase 5 语义匹配），我希望用字段语义向量近邻检索，把用户口语映射到字段。
2. 作为**下游 Agent**（Phase 6 计划生成），我希望查最短 JOIN 路径与关联表，规划多步查询。
3. 作为**管理员**，我希望在管理端看到表关系图谱（显式 + 推断外键），以便可视化确认。
4. 作为**系统**，我希望在元数据学习完成后自动把知识库刷新到最新，无需人工搬运。

## 术语（待团队确认后落 `spec/CONTEXT.md`）

| 术语 | 定义（初稿） |
|------|------|
| 知识库 | Phase 3 产出的、供下游消费的向量索引 + 图谱的合称。 |
| 字段语义向量（field_descriptions） | Milvus Collection，每列一条，文本 = 语义描述（向量化输入待定）。 |
| 知识图谱 | Neo4j 图，节点 Table/Column，边 CONTAINS/REFERENCES/INFERRED_REF/SAME_MEANING/JOINS_WITH。 |

## 范围内（本规格）

- **3.1 向量库（Milvus）— 仅 `field_descriptions`**：嵌入字段语义描述、基本 CRUD、增量更新。
- **3.2 图谱构建（Neo4j）**：从元数据 + 学习结果建全图（Table/Column 节点 + 五种边），含增量/重建策略。
- **3.3 图谱查询能力**：最短 JOIN 路径、关联表查找、JOIN 频次统计与排序。

## 范围外 / 延期

- **3.4 热词词典**、**3.5 值映射中心** —— 与 Phase 4（查询值标准化：枚举/区域/简称）职责重叠，拆到 Phase 3.b 或并入 Phase 4 单独细化，避免归属泥潭。
- **`query_samples` 向量集合** —— 依赖查询历史（Phase 5+ 运行期才有），本规格后置。
- 向量库 / 图谱的管理端 CRUD UI（Phase 10 管理端统一做）；本规格只做后端能力 + 必要 API。
- SAME_MEANING 边的自动产出（依赖跨表同义识别，可能需 LLM；先只建显式 + 推断外键边，SAME_MEANING 暂留空或手工）。
- 语义匹配 / SQL 生成 / 多步编排（Phase 5/6）。

## 行为规格 — 构建触发与同步（已定）

- **触发**：链在 `run_learning` 之后（复用 Phase 2 两触发点：首次提取后 auto + 手动重跑）。学习完成即刷新知识库，保证与最新学习结果一致。
- **图谱（Neo4j）**：每次按激活数据源**全量重建**（先删该源节点/边、再建）。纯 Cypher 读应用库，无外部调用；V1 不做蓝绿/双图，重建即覆盖、短暂不可用可接受。
- **向量（Milvus `field_descriptions`）**：**增量 upsert**，按 `column_id` 为键，只嵌入新增/变化的 `semantic_description`；冷启动首跑等价全量。避免 fill-once 下重复嵌入的成本。
- **数据源隔离**：图谱节点与向量记录均带 `data_source_id`；激活切换**不擦旧源**，只为新激活源构建（若未建过）；所有查询按「当前激活源」过滤，避免切换抖动。

## 行为规格 — 图谱构建与查询（已定）

- **节点**：`(:Table {data_source_id, schema, name, row_count})`、`(:Column {data_source_id, table, name, type, is_pk, nullable})`，均带 `data_source_id` 命名空间。
- **V1 边**（仅有数据来源的三种）：
  - `CONTAINS`（Table→Column）：来自 Phase 1 元数据。
  - `REFERENCES{confidence}`（Column→Column）：来自显式外键 `metadata_foreign_keys`（confidence=1.0）。
  - `INFERRED_REF{confidence}`（Column→Column）：来自 Phase 2 `metadata_inferred_fks`，**全部入图**，confidence 作边属性，查询侧按需过滤（不在构建期裁剪）。
- **不建（延期）**：`SAME_MEANING`（V1 无自动来源，留空）、`JOINS_WITH{frequency}`（依赖查询历史，Phase 5+）。
- **3.3 查询 V1**：最短 JOIN 路径（遍历 CONTAINS+REFERENCES+INFERRED_REF）+ 关联表查找；**JOIN 频次排序延期**（无查询历史数据）。

## 行为规格 — 向量库 field_descriptions（已定）

- **嵌入文本**：`"{表名}.{列名}：{semantic_description}"`（描述为主、表列上下文消歧）；表有语义描述时可前置（如 `"订单表.orders.status：订单状态"`）。
- **入库范围**：只索引 `semantic_description IS NOT NULL` 的列；未覆盖列不入向量库（与 Phase 2 覆盖率口径一致——未覆盖即无法被语义匹配命中）。
- **payload**：`column_id`、`data_source_id`、`table`、`column`、`description_source`、`description_confidence`（供下游过滤/排序，不参与嵌入）。
- **增量判定**：按 `semantic_description` 文本是否变化触发重嵌入；`description_confidence` 等其他字段变化不触发。

## 行为规格 — 嵌入与失败处理（已定）

- **嵌入服务**：走配置的本地 `bge-large-zh-v1.5`（`:8001`，1024 维，batch/截断走 `EMBEDDING_BATCH_SIZE` / `EMBEDDING_MAX_INPUT_LENGTH`）；与 Milvus/Neo4j 同列为本期运行时依赖（假设可用，属实现前置，不阻塞规格）。
- **两库独立**：图谱构建（纯 Cypher）与向量 upsert（依赖嵌入服务）相互独立；图谱可靠、几乎不失败，向量可能因嵌入服务抖动失败。
- **失败处理**：向量 upsert 失败**抑制 + 记日志**、跳过失败列，**不阻断**图谱构建，也不阻断学习流水线（沿用 Phase 2 的 suppress-and-continue）；失败列在下次学习重跑时重试（增量 upsert 幂等）。
- **数据治理**：嵌入对象是派生的 `semantic_description`（非原始业务数据）、用本地模型，**无外发、无 PII 风险**（与 Phase 2 L2 外发约束无关）。

## 验收口径

**应通过**：
- 学习完成后，激活源下 `semantic_description IS NOT NULL` 的列在 Milvus `field_descriptions` 各有一条向量，嵌入文本 = `表.列：描述`，payload 含 `column_id`/`data_source_id`/`table`/`column`/`description_source`/`description_confidence`。
- 向量近邻检索「订单的状态」→ 命中 `orders.status`（而非 `customers.status`），证明表列上下文消歧生效。
- 图谱含该源全部 Table/Column 节点 + `CONTAINS`/`REFERENCES`/`INFERRED_REF` 边；`INFERRED_REF` 边带 `confidence`。
- 最短 JOIN 路径查询 `orders ↔ customers` 返回经由 `customer_id` 的路径（用显式或推断外键）。
- 重跑学习：图谱按源全量重建（旧边先删后建）；向量只 upsert 新增/变化的描述，未变列不重嵌入。
- 嵌入服务不可用：图谱仍建成，向量 upsert 失败被抑制+记日志，学习流水线状态不受影响，下次重跑补齐。
- 激活切换到新数据源：新源被构建（不擦旧源）；查询按当前激活源过滤。

**应失败 / 边界**：
- 未覆盖列（`semantic_description` 为空）不入向量库（检索不到）。
- 低置信度（如 0.65）的 `INFERRED_REF` 边仍在图中（构建期不裁剪），由查询侧按 `confidence` 过滤。
- 跨数据源的最短路径查询**不应**串联两个源的节点（按 `data_source_id` 隔离）。
- 向量/图谱查询仅返回当前激活数据源的内容。

## 轻量风险扫尾

- **无 P0**。
- **P1**：嵌入服务（`:8001`）可用性是实现前置——dev/test 需启动；规格假设可用，失败处理 A（非致命+重试）已覆盖运行期抖动。
- **P2**：`SAME_MEANING` / `JOINS_WITH{frequency}` 延期 → Phase 6 多步查询的「JOIN 频次排序」在 V1 不可用（已知退化，需在 Phase 5/6 规格显式标注）。
- **P2**：图谱全量重建期短暂不可用（V1 接受；高并发/在线场景需蓝绿双图，延期）。
- **P3**：`query_samples` 向量集合延期（依赖 Phase 5+ 查询历史）。

## 开放问题（均已决议或转延期）

1. ~~范围切片~~ → 方案 A（核心三件套）。
2. ~~触发/同步模型~~ → 方案 A（链式 + 图谱全量 + 向量增量 + 按源隔离）。
3. ~~图谱边范围~~ → 方案 A（V1 三边全入，SAME_MEANING/JOINS_WITH 延期）。
4. ~~向量化文本~~ → 方案 A（`表.列：描述`，只索引已覆盖列）。
5. ~~嵌入/失败处理~~ → 方案 A（两库独立、向量非致命+重试）。
6. **延期项**（非阻塞，落后续 issue/规格）：`SAME_MEANING` 来源（人工/LLM）、`JOINS_WITH` 频次（待查询历史）、`query_samples`（待查询历史）、3.4 热词词典 / 3.5 值映射中心（归 Phase 3.b 或 Phase 4）。

## Change Log

- 2026-06-19（第 1 轮）：确认范围切片 = 方案 A（核心三件套：向量库 `field_descriptions` + 图谱构建 + 图谱查询）；3.4/3.5 延期；`query_samples` 后置。
- 2026-06-19（第 2 轮）：确认触发/同步模型 = 方案 A（链式触发 + 图谱全量重建 + 向量增量 upsert + 按 `data_source_id` 隔离不擦旧 + 无蓝绿）。原「数据源隔离」开放问题并入行为规格闭合。
- 2026-06-19（第 3 轮）：确认图谱边范围 = 方案 A（V1 建 CONTAINS/REFERENCES/INFERRED_REF 全入、confidence 作属性；SAME_MEANING、JOINS_WITH 延期；3.3 只做最短路径 + 关联表，频次排序延期）。
- 2026-06-19（第 4 轮）：确认向量化文本 = 方案 A（`表.列：描述` 拼接、只索引已覆盖列、按描述文本变化增量）。
- 2026-06-19（第 5 轮）：确认嵌入/失败处理 = 方案 A（两库独立、向量失败抑制+日志+下次重试、不阻断；本地模型无外发）。补全验收口径与风险扫尾，规格 refining 完成，待 `team-spec-review`。
