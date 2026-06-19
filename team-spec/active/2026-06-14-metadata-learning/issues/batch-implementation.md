# 批量实现报告 — 元数据学习（Phase 2）

- **slug**：`2026-06-14-metadata-learning`
- **执行日期**：2026-06-19
- **批量范围**：3 个 AFK issue（001/002/003），按 PRD 耦合关系重排为 003 → 002 → 001
- **结果**：3/3 完成，均 `ready for PR`

## 本轮队列与执行顺序

| 顺序 | Issue | 标题 | 验证状态 |
|---|---|---|---|
| 1 | 003 | 收紧 L2 推断：不发原始行、每表独立会话、加调用数上限 | ready for PR |
| 2 | 002 | 修正学习覆盖率口径为按语义描述非空列占比 | ready for PR |
| 3 | 001 | 推断跨表值重叠外键关系并写入推断外键表 | ready for PR |

重排理由（无硬依赖，仅发布顺序耦合）：先让 L2 真正可用（003），再让覆盖率真实化（002）才不会把 L2 静默失效误报为回归；001（FK 推断）独立，放最后。

## 跳过 / 阻塞

- 无。3 个 issue 全部 AFK，无 HITL 决策点，无 blocker。

## 关键验证命令与结果

```text
pytest test/test_learning/                         → 127 passed
pytest test/test_learning/test_l2_inference.py     → 全部通过（重写后）
pytest test/test_learning/test_l2_orchestrator.py  → 全部通过（新签名 + 并发/上限/不发原始行）
pytest test/test_learning/test_learning_coverage.py→ 4 passed（含 2 个先 RED 后 GREEN）
pytest test/test_learning/test_fk_inference.py     → 20 passed（纯函数 + 集成）
pytest（全量）                                      → 206 passed, 1 failed*
ruff check / format（src/learning、src/config、src/metadata/models.py）→ clean
alembic upgrade head / downgrade -1 / upgrade head  → 迁移可正反向执行
```

\* `test_config/test_settings.py::test_default_encryption_key_is_empty`：**预存环境问题**，项目 `.env` 设了 `ENCRYPTION_KEY`，与本批无关（`ENCRYPTION_KEY=""` 时通过）。本批未触碰 `encryption_key` 或该测试。

## 主要变更

- **003**：`src/learning/l2_inference.py`（移除取样、改结构化信号 prompt、`FieldSignal`）、`src/learning/orchestrator.py`（`run_l2_inference` 改 session factory + 每表独立会话 + `max_calls` 提前停）、`src/config/database.py`（`get_session_factory`）、`src/config/settings.py` + `.env.example`（`learning_l2_max_calls`）。
- **002**：`src/learning/orchestrator.py`（`run_learning` 覆盖率改查库 `semantic_description IS NOT NULL`、`l1_count` 仅拆词、`total_columns==0→failed`）。
- **001**：`src/metadata/models.py`（`MetadataInferredForeignKey`）、`alembic/versions/a1c7e9f40b2d_*.py`（新表迁移）、`src/learning/fk_inference.py`（新模块）、`src/learning/orchestrator.py`（`_run_fk_inference_with_ds` + 接入 `run_learning` + 修 [D2] docstring）。
- 测试：`test/test_learning/conftest.py`（共享 `engine`/`session_factory` 夹具 + 清理新表）、`test_l2_inference.py`（重写）、`test_l2_orchestrator.py`（重写）、`test_learning_coverage.py`（新）、`test_fk_inference.py`（新）、`test_settings_and_models.py`（+2）。

## 未提交本地变更

- 所有变更停留在本地工作区，**未执行 `git commit` / `git push` / 创建 PR**，可供 `team-issue-verify` 复查或直接进入 PR 创建。

## 剩余队列 / 人工介入

- 无。本批 3 个 issue 已全部实现并验证；无后续队列，无 HITL。
