# 学习后自动刷新知识库并在删除数据源时清理

## Parent

PRD：`team-spec/active/2026-06-19-knowledge-base/prd/prd.md`（知识库生命周期：刷新接入 + DS 删除清理，issue D）

## What to build

把知识库接入元数据生命周期，形成「随学习自动一致」的闭环：
1. **学习后自动刷新**：在 `run_learning` 末尾增加**独立、失败抑制**的知识库刷新步骤（对激活源调用 #1 的向量增量 upsert + #2 的图谱全量重建）；该步骤**不参与学习状态判定**，向量失败抑制+记日志、下次重跑补齐。
2. **数据源删除清理**：数据源被删除时，清理 Milvus/Neo4j 中该源的节点/边/向量记录（应用库 CASCADE 不级联到外部存储，需显式清理，避免孤儿）。

## Type

AFK（可独立执行，无需人工决策）—— 刷新为末尾 suppress 步骤、不进状态判定、DS 删除即时清理均已在 PRD 钉死。

## Acceptance criteria

- [x] Given 学习完成，When `run_learning` 结束，Then 自动触发激活源的知识库刷新（图谱全量重建 + 向量增量 upsert）。
- [x] Given 嵌入服务不可用，When 学习完成，Then 图谱照常建成、向量 upsert 失败被抑制+记日志、学习日志状态不受影响、下次重跑补齐失败列。
- [x] Given 知识库刷新步骤抛错，When `run_learning` 运行，Then 该错误被抑制（不进入学习状态判定），L0/L1/L2/FK 推断等其余步骤照跑。
- [x] Given 一个数据源被删除，When 删除完成，Then Milvus/Neo4j 中该源的节点/边/向量记录全部清理、无孤儿。
- [x] Given 激活切换到新数据源并触发学习，When 刷新运行，Then 新源构建、旧源图谱/向量保留。
- [x] 相关集成测试（学习后两库就绪、删源无孤儿、嵌入失败非致命、切换不擦旧）infra-gated。

## Blocked by

- #1（向量库刷新/清理 API）
- #2（图谱重建/清理 API）

## Notes

- 刷新步骤以 `contextlib.suppress(Exception)` 包裹，挂在 `run_learning` 末尾、学习状态判定之外（参考 Phase 2 FK 推断的 suppress 模式）。
- DS 删除清理复用 #1/#2 提供的「按 `data_source_id` 清理」能力；需在数据源删除链路挂清理调用。
- 运行时依赖（Milvus/Neo4j/嵌入服务）就绪是集成验证前置；纯逻辑（触发编排、清理调度）可单测。
- 发布顺序：依赖 #1+#2；可与 #3 并行。

## Publish Status

- Status: created
- Updated At: 2026-06-19T05:00:15Z
- GitHub Number: 21
- GitHub URL: https://github.com/yanheng799/chat-db/issues/21

## Status

ready for PR

## Implementation Notes

- 新增 `src/knowledge/lifecycle.py`：`refresh_knowledge_base`（仅激活源；向量构建 try/except 非致命、图谱独立构建；整体不抛错）、`cleanup_knowledge_base`（删 Milvus + Neo4j，各自 best-effort）。
- 接入 `run_learning`：在学习日志 commit 后追加 `with contextlib.suppress(Exception): await _refresh_knowledge_with_ds(session, data_source_id)`（不进状态判定）；`_refresh_knowledge_with_ds` 构造默认 `VectorStore`/`GraphStore`/`EmbeddingClient`。
- 接入数据源删除：`delete_data_source` 在 commit 后 `suppress(Exception)` 调 `cleanup_knowledge_base`（应用库 CASCADE 不级联到外部存储）。
- 顺手修一个 #18 遗留边界：`collect_covered_fields` 对 `description_source=None` 兜底为 `""`（Milvus VARCHAR 拒绝 nil，否则 covered-but-sourceless 列会 upsert 失败）。
- 测试 `test/test_knowledge/test_lifecycle.py`（真实 Milvus/Neo4j/嵌入 + run_learning 接线 monkeypatch）。

## Verification

- `pytest test/test_knowledge/test_lifecycle.py` → **5 passed**。
- 全量 `pytest` → **233 passed, 1 failed**（`test_default_encryption_key_is_empty` 预存环境问题，与本批无关）。
- `ruff check`（src/knowledge、orchestrator、datasources、test_knowledge）→ clean。
- 注：`ruff check src/ test/` 全局报 38 处 lint 错误，均位于**既有**测试文件（test_api/test_config/test_db/test_learning/test_metadata），非本批引入、不影响测试通过，留作既有技术债。
