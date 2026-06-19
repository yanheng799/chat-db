## Parent

PRD：`team-spec/active/2026-06-14-metadata-learning/prd/prd.md`（偏差 B，覆盖率口径失真）

## What to build

修正学习覆盖率与状态判定。覆盖率改为按该数据源下 `semantic_description` **非空**列数 / 总列数计算，不再用 l0+l1+l2 叠加计数（当前实现把模式检测写入 `null_ratio` 的列也计入「已描述」、并可能与 L0 双计，导致比值几乎恒 ≥0.8、甚至 >100%，`success` 判定失效）。`l1_count` 语义修正为**仅拆词成功**计数；模式检测写入结构统计字段但**不计入「已描述」**。状态判定：覆盖率 ≥0.8 → `success`、>0 → `partial_success`、=0 → `failed`；总列数=0 → `failed`（无可描述列，且不发生除零）。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [x] Given 一数据源模式检测给多数列写了 `null_ratio` 但这些列无 `semantic_description`，When 学习运行，Then 这些列不计入「已描述」，覆盖率不因此虚高。
- [x] Given 覆盖率（`semantic_description` 非空列数 / 总列数）≥0.8，When 学习运行，Then `status=success`；>0 且 <0.8 → `partial_success`；=0 → `failed`。
- [x] Given 总列数=0 的数据源，When 学习运行，Then `status=failed`，且不发生除零错误。
- [x] Given 同一批列，When 学习运行，Then 学习日志 `columns_described` 与「`semantic_description` 非空列数」一致，不会出现 >100%。
- [x] Given 模式检测与拆词对同一列各写不同字段，When 学习运行，Then `l1_count` 仅计拆词成功列，模式检测不重复计入「已描述」。
- [x] 相关行为测试通过公共入口验证覆盖率与状态判定（含「模式检测写 `null_ratio` 不虚高」与「总列数=0」边界）。

## Blocked by

- None - can start immediately

## Notes

- 无 schema 变更，纯代码与测试。
- **发布顺序耦合（非硬依赖）**：建议与 Issue 003（L2 修复）同批或在其后落地。单独修本 issue 会让覆盖率真实化，从而把 L2 在默认并发下的静默失效暴露为大面积 `partial_success`/`failed`；Issue 003 让 L2 真正可用后两者口径一致。两者无构建依赖，可独立实现与验证。
- 修正后 V1 因不下发原始行，含大量无注释列的 schema 可能普遍 `partial_success`，属预期（见 PRD 业务规则）；自动监控/告警延 Phase 11。

## Status

ready for PR

## Implementation Notes

- `run_learning` 中覆盖率改为直接查库：`SELECT count(*) WHERE table_id IN (...) AND semantic_description IS NOT NULL`，不再用 `l0+l1+l2` 叠加（旧法把模式检测写 `null_ratio` 的列计入，导致比值虚高甚至 >100%）。
- `l1_count` 改为仅拆词成功数（`l1_split_count`）；模式检测不再计入「已描述」，其返回值也不再捕获（仅作为副作用写结构统计字段）。
- 状态判定：`total_columns == 0 → failed`（修复旧法 `total_columns==0 → success` 的错误，并避免除零）；否则按非空占比 `≥0.8 success / >0 partial / =0 failed`。
- 改动文件：`src/learning/orchestrator.py`（`run_learning`）；新增测试 `test/test_learning/test_learning_coverage.py`。

## Acceptance Criteria Coverage

- AC1（模式检测写 `null_ratio` 不虚高）→ `test_coverage_not_inflated_by_pattern_detection`（monkeypatch 模式检测返回 100，断言 `columns_described==0`、`status==failed`；旧码此处返回 100/success，RED→GREEN）。
- AC2（success/partial/failed 按非空占比）→ `test_success_when_fully_covered`（3/3 success）、`test_partial_success_reflects_real_coverage`（3/5 partial）。
- AC3（总列数=0 → failed、不除零）→ `test_empty_data_source_is_failed`（旧码返回 success，RED→GREEN）。
- AC4（`columns_described`==非空计数、不 >100%）→ 上述 inflation 测试（0 而非 100）+ partial 测试（3）。
- AC5（`l1_count` 仅拆词）→ inflation 测试中模式检测返回 100 但 `columns_described` 仍为 0，证明模式检测未计入。
- AC6（公共接口行为测试）→ 全部通过 `run_learning` 公共入口验证。

## Verification

- `pytest test/test_learning/test_learning_coverage.py` → 4 passed（含 2 个先 RED 后 GREEN 的回归驱动）。
- `pytest test/test_learning/` → 107 passed，无回归。
- `ruff check` / `ruff format`（src/learning/orchestrator.py）→ clean。
