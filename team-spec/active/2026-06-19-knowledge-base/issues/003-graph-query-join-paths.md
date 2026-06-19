# 在知识图谱上查询最短 JOIN 路径与关联表

## Parent

PRD：`team-spec/active/2026-06-19-knowledge-base/prd/prd.md`（3.3 图谱查询，issue C）

## What to build

在已建好的知识图谱上提供查询能力：两表间**最短 JOIN 路径**（遍历 `CONTAINS`/`REFERENCES`/`INFERRED_REF`）与**关联表查找**；按当前激活 `data_source_id` 过滤、不跨源串联；支持按 `confidence` 过滤 `INFERRED_REF` 边（如仅走置信度 ≥ 阈值的推断边）。

## Type

AFK（可独立执行，无需人工决策）—— 查询语义、按源过滤、按置信度过滤均已在 PRD 钉死。

## Acceptance criteria

- [x] Given `orders` 与 `customers` 经由 `customer_id`（显式或推断外键），When 查最短 JOIN 路径，Then 返回经由 `customer_id` 的路径。
- [x] Given 两表之间无任何 FK/INFERRED_REF 路径，When 查，Then 返回空（不伪造路径）。
- [x] Given 分属两个数据源的两表，When 查最短路径，Then 不串联两源节点（按 `data_source_id` 过滤）。
- [x] Given 某表，When 查其关联表，Then 返回同源内经 `REFERENCES`/`INFERRED_REF` 可达的关联表。
- [x] Given 设置 confidence 阈值，When 查路径，Then 仅遍历 `confidence ≥ 阈值` 的 `INFERRED_REF` 边。
- [x] 相关单测（路径构造/过滤、跨源隔离、置信度过滤）通过；端到端集成测试 infra-gated（需 Neo4j + 已建图谱，依赖 #2）。

## Blocked by

- #2（需 #2 构建的图谱才能查/验）

## Notes

- 仅遍历 V1 三边（`CONTAINS`/`REFERENCES`/`INFERRED_REF`）；无 `SAME_MEANING`/`JOINS_WITH`。
- 最短路径用 Neo4j `shortestPath` Cypher；查询始终按激活源过滤。
- 发布顺序：依赖 #2；可与 #4 并行（#4 依赖 #1+#2，不依赖本查询能力）。

## Publish Status

- Status: created
- Updated At: 2026-06-19T05:00:13Z
- GitHub Number: 20
- GitHub URL: https://github.com/yanheng799/chat-db/issues/20

## Status

ready for PR

## Implementation Notes

- 新增 `src/knowledge/graph_query.py`：`shortest_join_path`（`shortestPath` 遍历 CONTAINS/REFERENCES/INFERRED_REF，按激活源过滤、支持 `min_confidence` 用 `WHERE all(r IN relationships(path) ...)` 过滤 INFERRED_REF）、`related_tables`（一度关联表）。`GraphStore` 增 `query()` 只读方法（neo4j 6.x 用 `list(session.run(...))`）。
- 路径解析 `_path_to_join_steps` 兼容 neo4j-driver 多版本的节点/关系 element id 取法。
- 测试 `test/test_knowledge/test_graph_query.py`（真实 Neo4j + build_graph）：直接 FK、两跳、无路径、关联表、置信度过滤、按源隔离。

## Verification

- `pytest test/test_knowledge/test_graph_query.py` → **6 passed**。
- `pytest test/test_knowledge/` → 22 passed（向量库 + 图谱构建 + 图谱查询，全真实 infra）。
- `ruff check/format` → clean。
