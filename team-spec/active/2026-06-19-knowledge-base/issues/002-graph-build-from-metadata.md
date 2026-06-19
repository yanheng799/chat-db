# 从元数据与推断外键构建知识图谱

## Parent

PRD：`team-spec/active/2026-06-19-knowledge-base/prd/prd.md`（3.2 图谱构建，issue B）

## What to build

实现 Neo4j 客户端，从应用库元数据 + 学习结果构建知识图谱：`(:Table)`/`(:Column)` 节点（均带 `data_source_id`，Table 含 schema/name/row_count，Column 含 table/name/type/is_pk/nullable）；边 `CONTAINS`（Table→Column）、`REFERENCES{confidence}`（显式外键，confidence=1.0）、`INFERRED_REF{confidence}`（来自 `metadata_inferred_fks`，全部入图、confidence 作边属性、构建期不裁剪）。按激活 `data_source_id` **全量重建**（先删该源节点/边、再建）。不建 `SAME_MEANING`/`JOINS_WITH`。

## Type

AFK（可独立执行，无需人工决策）—— 节点/边模型、三边全入、按源全量重建、不裁剪置信度均已在 PRD 钉死。

## Acceptance criteria

- [x] Given 激活源有表/字段/显式+推断外键，When 构建图谱，Then Neo4j 含该源全部 Table/Column 节点 + `CONTAINS` + `REFERENCES{confidence}` + `INFERRED_REF{confidence}` 边，节点/边带 `data_source_id`。
- [x] Given 该源已有图谱，When 重跑构建，Then 先删该源节点/边再重建（全量重建，不叠加）。
- [x] Given 推断外键 confidence=0.65 与 0.8 各一条，When 构建，Then 两者均入图、`confidence` 作边属性（构建期不裁剪）。
- [x] Given 多个数据源，When 构建，Then 各源节点/边按 `data_source_id` 隔离、不混。
- [x] Given 表/列来自 `metadata_tables`/`metadata_columns`、外键来自 `metadata_foreign_keys`/`metadata_inferred_fks`，When 构建，Then 节点与边完整映射、字段类型/PK 等属性正确。
- [x] 相关单测（节点/边构造、按源隔离、全量重建先删逻辑）通过；端到端集成测试 infra-gated（需 Neo4j 就绪）。

## Blocked by

- None - can start immediately

## Notes

- Neo4j 节点/边均带 `data_source_id`；建议索引 `Table(name)`/`Column(name)` + `data_source_id` 以加速后续最短路径查询。
- `neo4j`（neo4j-driver）已声明；`src/knowledge/` 从零实现客户端。
- 只读应用库（`metadata_*` + `metadata_inferred_fks`，后者来自 [PR #17](https://github.com/yanheng799/chat-db/pull/17)）；不访问目标业务库。
- 发布顺序：可与 #1 并行；#3（图谱查询）依赖本 issue。

## Publish Status

- Status: created
- Updated At: 2026-06-19T05:00:11Z
- GitHub Number: 19
- GitHub URL: https://github.com/yanheng799/chat-db/issues/19

## Status

ready for PR

## Implementation Notes

- 新增 `src/knowledge/graph_store.py`：`GraphStore`（Neo4j driver 封装：`rebuild` 全量重建、`delete_by_data_source`、`count_nodes/count_edges`）；uid 函数 `table_uid`/`column_uid`（按 `data_source_id|schema.table.column`）；`build_graph` 从应用库读 `metadata_tables`/`metadata_columns`/`metadata_foreign_keys`/`metadata_inferred_fks` 组装节点 + CONTAINS/REFERENCES{confidence=1.0}/INFERRED_REF{confidence} 边，两端列必须存在才建边。
- 全量重建：先 `MATCH (n {data_source_id:$ds}) DETACH DELETE n`，再建。节点/边均带 `data_source_id`；构建期不按 confidence 裁剪。
- neo4j 6.2.0 driver；`src/knowledge/` 从零实现。测试 `test/test_knowledge/test_graph_store.py` + conftest `neo4j_store` 夹具（真实 Neo4j，per-test wipe）。

## Verification

- `pytest test/test_knowledge/test_graph_store.py` → **5 passed**（真实 Neo4j 集成：节点/边计数、confidence 存边、全量重建替换、多源隔离、按源删除）。
- `ruff check/format` → clean。
