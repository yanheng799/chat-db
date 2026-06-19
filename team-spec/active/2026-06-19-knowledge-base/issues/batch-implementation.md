# 批量实现报告 — 知识库构建（Phase 3）

- **slug**：`2026-06-19-knowledge-base`
- **执行日期**：2026-06-19
- **批量范围**：4 个 AFK issue（GitHub #18–#21），顺序 #18/#19 并行 → #20（依赖 #19）、#21（依赖 #18+#19）
- **结果**：4/4 完成，均 `ready for PR`

## 本轮队列与执行顺序

| 顺序 | Issue | GitHub | 标题 | 验证状态 |
|---|---|---|---|---|
| 1 | 001 | #18 | 为已覆盖字段构建语义向量并支持近邻检索 | ready for PR |
| 2 | 002 | #19 | 从元数据与推断外键构建知识图谱 | ready for PR |
| 3 | 003 | #20 | 在知识图谱上查询最短 JOIN 路径与关联表 | ready for PR |
| 4 | 004 | #21 | 学习后自动刷新知识库并在删除数据源时清理 | ready for PR |

## 跳过 / 阻塞

- 无。4 个 issue 全部 AFK，无 HITL，无 blocker。infra（Milvus/Neo4j/嵌入服务 :8001）经探测可用，集成测试用真实服务验证。

## 关键验证命令与结果

```text
pytest test/test_knowledge/                           → 27 passed（向量库 + 图谱构建 + 图谱查询 + 生命周期，全真实 infra）
pytest（全量）                                         → 233 passed, 1 failed*
ruff check（src/knowledge、orchestrator、datasources、test_knowledge） → clean
```

\* `test_config/test_settings.py::test_default_encryption_key_is_empty` 预存环境问题（项目 `.env` 设了 `ENCRYPTION_KEY`），与本批无关。

## 主要变更（src/knowledge/ 从空到 4 模块）

- **#18 向量库**：`embedding.py`（EmbeddingClient，批量调本地 `:8001/v1/embeddings`）、`vector_store.py`（Milvus `field_descriptions`：1024 维 cosine+HNSW、按 `column_id` 增量 upsert 方案 A、按源 query/search/delete；纯函数 `build_field_text`/`compute_upsert_plan`；`build_field_vectors`/`search_fields`）。
- **#19 图谱构建**：`graph_store.py`（Neo4j `GraphStore`：Table/Column 节点 + CONTAINS/REFERENCES/INFERRED_REF 边、按源全量重建、delete_by_data_source、count；`build_graph` 从应用库读元数据 + 推断外键组装）。
- **#20 图谱查询**：`graph_query.py`（`shortest_join_path` 用 shortestPath 遍历三边、按源过滤、`min_confidence` 过滤 INFERRED_REF；`related_tables`；GraphStore 增 `query()`）。
- **#21 生命周期**：`lifecycle.py`（`refresh_knowledge_base` 向量非致命+图谱独立、`cleanup_knowledge_base`）；接入 `run_learning` 末尾 suppress 步骤 + `delete_data_source` 清理钩子。
- **依赖/兼容**：pymilvus 3.0.0（`prepare_index_params`、`consistency_level="Strong"`）、neo4j 6.2.0（`list(session.run(...))`）。
- **测试基建**：`test/test_knowledge/`（conftest：真实 PG `db_session` + 真实 Milvus `milvus_store` + 真实 Neo4j `neo4j_store` + 真实 `embedding_client`）。

## 未提交本地变更

- 所有变更停留在本地工作区（`main` 分支，未提交），**未执行 `git commit` / `git push` / 创建 PR**。可供 `team-issue-verify` 复查或进入 PR 创建。

## 剩余队列 / 人工介入

- 无。本批 4 个 issue 已全部实现并验证；无后续队列，无 HITL。
- 既有技术债（非本批）：`ruff check src/ test/` 全局 38 处 lint 错误位于既有测试文件，留作后续清理。
