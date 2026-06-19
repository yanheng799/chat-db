# 为已覆盖字段构建语义向量并支持近邻检索

## Parent

PRD：`team-spec/active/2026-06-19-knowledge-base/prd/prd.md`（3.1 向量库，issue A）

## What to build

为激活数据源下**已覆盖**的字段（`semantic_description IS NOT NULL`）构建语义向量库：实现 Milvus 客户端 + 嵌入客户端，创建 `field_descriptions` collection（1024 维、cosine、HNSW），按 `column_id` 为键**增量 upsert**——仅嵌入「`semantic_description` 文本相比已嵌入版本有变化」的列（方案 A：查 Milvus 已存 payload 与应用库比对，无 schema 变更）。嵌入文本 = `"{表名}.{列名}：{semantic_description}"`（表列上下文消歧）。提供按激活 `data_source_id` 过滤的近邻检索。未覆盖列不入库。

## Type

AFK（可独立执行，无需人工决策）—— cosine+HNSW、增量方案 A、嵌入文本 `表.列:描述`、只索引已覆盖列均已在 PRD 钉死。

## Acceptance criteria

- [x] Given 激活源有已覆盖字段，When 构建向量库，Then Milvus `field_descriptions` 每个该字段一条向量，嵌入文本 = `表.列：描述`，payload 含 `column_id`/`data_source_id`/`table`/`column`/`description_source`/`description_confidence`。
- [x] Given 未覆盖列（`semantic_description` 为空），When 构建，Then 不入库。
- [x] Given 向量近邻检索「订单的状态」（按激活源过滤），When 查询，Then 命中 `orders.status` 而非 `customers.status`（表列上下文消歧生效）。
- [x] Given 已嵌入列的描述文本未变，When 重跑构建，Then 该列不重嵌入（按 `column_id` + 描述文本变化判定，方案 A 查 Milvus 比对）。
- [x] Given 新增或描述变化的列，When 重跑，Then 只 upsert 这些列。
- [x] Given 跨数据源检索，When 查询，Then 结果按 `data_source_id` 过滤、不跨源。
- [x] 相关单测（嵌入文本构造、增量比对、源过滤）通过；端到端集成测试 infra-gated（需 Milvus + 嵌入服务就绪）。

## Blocked by

- None - can start immediately

## Notes

- Milvus collection：1024 维、**cosine** 度量、**HNSW** 索引。
- 嵌入服务：本地 `bge-large-zh-v1.5` @ `:8001`（`config.settings.embedding_*` 已就绪）；`pymilvus>=2.6` 已声明。
- `src/knowledge/` 当前为空，客户端从零实现。
- 增量方案 A（查 Milvus 比对）为自包含、无应用库 schema 变更、无迁移。
- 只读应用库 Phase 2 元数据（`semantic_description` 等）；不访问目标业务库。
- 发布顺序：可与 #2 并行。

## Publish Status

- Status: created
- Updated At: 2026-06-19T05:00:09Z
- GitHub Number: 18
- GitHub URL: https://github.com/yanheng799/chat-db/issues/18

## Status

ready for PR

## Implementation Notes

- 新增 `src/knowledge/embedding.py`（`EmbeddingClient`，批量调本地 `:8001/v1/embeddings`）与 `src/knowledge/vector_store.py`（`VectorStore` Milvus 客户端：建 collection 1024 维 cosine+HNSW、upsert、按源 query/search/delete；纯函数 `build_field_text` / `compute_upsert_plan`；编排 `build_field_vectors` 增量 upsert + `search_fields`）。
- pymilvus 3.0.0：`MilvusClient` + `client.prepare_index_params()`（无顶层 `IndexParams`）；query/search 用 `consistency_level="Strong"` 保证 upsert 后立即可见。
- 增量方案 A：`list_embed_texts` 取已存 `description_text` 与当前 embed 文本比对，仅 upsert 变化/新增列。
- 测试：`test/test_knowledge/`（conftest 含真实 PG `db_session` + 真实 Milvus `milvus_store` + 真实 `embedding_client`）+ `test_vector_store.py`。

## Verification

- `pytest test/test_knowledge/test_vector_store.py` → **11 passed**（真实 Milvus + 嵌入服务集成 + 纯函数单测）。
- `ruff check/format`（src/knowledge、test/test_knowledge）→ clean。
