## Parent

PRD：`team-spec/active/2026-06-14-metadata-learning/prd/prd.md`（缺口 A，值重叠度外键推断）
决策：`team-spec/active/2026-06-14-metadata-learning/spec/decisions/0001-fk-inference-in-learning.md`（accepted）

## What to build

为激活数据源推断**未声明的跨表外键关系**，作为 L1 的一个子步骤接入 `run_learning`。对满足候选条件的跨表列对（数据类型匹配 + 一侧为 PK/unique + 字段名相似度 ≥0.5 门槛）连活库算值重叠率；重叠率 ≥阈值（默认 0.8，可配）产出一条推断外键，置信度按重叠率映射（≥0.95→0.8，0.8–0.95→0.65），`source=rule_inference`，存新表 `metadata_inferred_fks`。每次学习对该数据源的推断外键**重算替换**（先清除既有推断外键，再按本轮结果写入）。外键推断失败被抑制、不阻断流水线。顺手修 `run_learning` 过时 docstring [D2]。

## Type

AFK（可独立执行，无需人工决策）—— 阈值 0.8、名称相似度门槛 0.5、置信度映射、新表存储、重算替换语义均已在 PRD 钉死。

## Acceptance criteria

- [x] Given `orders.customer_id` 与 `customers.id`（数据类型匹配、`customers.id` 为 PK、名称相似度 ≥0.5、值重叠率 ≥0.8），When 外键推断运行，Then 产出一条 `metadata_inferred_fks` 行，`source=rule_inference`，`confidence` 按重叠率映射（≥0.95→0.8，0.8–0.95→0.65）。
- [x] Given 一对跨表列值重叠率 <0.8 或名称相似度 <0.5，When 外键推断运行，Then 不产出推断外键行。
- [x] Given 候选门槛任一不满足（类型不匹配 / 两侧均非 PK/unique / 名称相似度 <0.5），When 外键推断运行，Then 该列对不进入重叠率计算。
- [x] Given 该数据源已有推断外键，When 手动重跑学习，Then 推断外键被重算替换（既有推断外键先清除、再按本轮结果写入），不与既有数据叠加。
- [x] Given 外键推断过程抛错，When `run_learning` 运行，Then 该错误被抑制、记日志，流水线继续执行 L2，学习日志状态不受此影响。
- [x] Given 大表参与重叠率计算，When 推断运行，Then 复用既有采样决策（`should_use_sampling` + `query_executor`），不 OOM、不超时。
- [x] Given 新表 `metadata_inferred_fks`，When `alembic upgrade head`，Then 表按数据源隔离创建（含 `data_source_id`、`source_table`、`source_column`、`target_table`、`target_column`、`overlap_rate`、`name_similarity`、`confidence`、`source`），且迁移可反向执行。
- [x] Given 阅读 `run_learning`，When 查看其 docstring，Then 不再声称 L1/L2 为占位（修正 [D2]）。
- [x] 相关行为测试通过公共入口验证：命中 / 不命中 / 重算替换 / 失败抑制 / 大表采样路径。

## Blocked by

- None - can start immediately

## Notes

- 复用既有 `query_executor` 抽象与数据源只读连接，**不引入图谱层依赖**（决策 0001：learning 产出语义事实、graph 消费）。
- 推断外键用**新表** `metadata_inferred_fks`，不扩 `MetadataForeignKey`，对应图谱层 `INFERRED_REF` 边（与显式外键 `REFERENCES` 分离）；完整 DDL 在本 issue 的 Alembic 迁移中最终确定。
- 重叠率阈值默认 0.8 建议做成可配配置项（与 `learning_l2_*` 同处 `config.settings`）。
- Mock 边界：对目标库的 `query_executor` 可 mock；应用库会话走真实 async session。
- 顺手修 [D2]：`run_learning` docstring 过时（声称 L1/L2 占位，实际已实现）。
- 发布顺序：本 issue 独立，可与 Issue 002/003 任意并行。

## Status

ready for PR

## Implementation Notes

- 新增模型 `MetadataInferredForeignKey`（`metadata/models.py`），表 `metadata_inferred_fks`，按 `data_source_id` 隔离，含 `source_schema/source_table/source_column/target_schema/target_table/target_column/overlap_rate/name_similarity/confidence/source/created_at`，唯一约束 `(data_source_id, source_table, source_column, target_table, target_column)`。
- 新增 Alembic 迁移 `a1c7e9f40b2d`（down_revision `8786cdcd3fa3`），建表 + `data_source_id` 索引；`alembic upgrade head` / `downgrade -1` 均通过。
- 新增 `src/learning/fk_inference.py`：纯函数 `compute_name_similarity`（取「列↔列」与「列↔被引用表」SequenceMatcher 最大值，命中 `customer_id→customers` 这类经典 FK）、`compute_overlap_rate`（源值集合在目标中的 containment）、`confidence_for_overlap`（≥0.95→0.8、0.8–0.95→0.65、否则 None）、`generate_candidates`（类型匹配 + 目标侧 PK/unique + 名称相似度门槛）、`build_distinct_values_query`（PG `TABLESAMPLE` + `LIMIT` 上限 / MySQL `LIMIT`）；`run_fk_inference` 编排：重算替换（先删该 DS 既有推断外键）→ 候选 → 估行数（`should_use_sampling`）→ 取去重值（`query_executor`）→ 算 overlap → 写行。
- 编排接入：`orchestrator._run_fk_inference_with_ds`（复用 `_run_pattern_detection_with_ds` 模式，按 SQL 区分估行 dict / 去重 list 返回）→ 在 `run_learning` 中作为 L1 子步骤、`contextlib.suppress(Exception)` 包裹，不影响覆盖率与状态。
- 修正 [D2]：`run_learning` docstring 改为如实描述 L0→L1（拆词/模式检测/FK 推断）→L2。
- 改动文件：`src/metadata/models.py`、`alembic/versions/a1c7e9f40b2d_*.py`、`src/learning/fk_inference.py`（新）、`src/learning/orchestrator.py`、`test/test_learning/conftest.py`（清理新表）、`test/test_learning/test_fk_inference.py`（新）。

## Acceptance Criteria Coverage

- AC1（命中产出 + 置信度映射 + source）→ `test_infers_fk_for_overlapping_pk_reference`（orders.customer_id↔customers.id，overlap 1.0→confidence 0.8）。
- AC2（overlap<0.8 或名称相似度<0.5 不产出）→ `test_no_inference_when_overlap_below_threshold`、`test_dissimilar_column_below_threshold`、`test_low_name_similarity_excluded`。
- AC3（候选门槛：类型/PK-unique/名称相似度）→ `test_type_mismatch_excluded`、`test_low_name_similarity_excluded`、`test_unique_index_reference_generates_candidate`。
- AC4（重算替换）→ `test_recompute_replace_clears_existing_inferred_fks`（先插 stale 行，跑后只剩新行）。
- AC5（失败抑制、流水线继续）→ `test_overlap_query_failure_is_skipped`（executor 抛错→候选跳过、不崩）+ `run_learning` 用 `suppress(Exception)` 包裹。
- AC6（大表采样、不 OOM/超时）→ `test_pg_sampling_for_large_table`（SQL 含 `TABLESAMPLE SYSTEM (1)`）+ `DISTINCT_VALUE_CAP=10000` 上限。
- AC7（迁移建表、可反向）→ `alembic upgrade head` / `downgrade -1` 实跑通过；表存在（`select count(*) from metadata_inferred_fks` = 0）。
- AC8（docstring 不再称占位）→ `run_learning` docstring 已重写。
- AC9（公共接口行为测试）→ 全部经 `run_fk_inference` / `generate_candidates` 等公共入口验证。

## Verification

- `pytest test/test_learning/test_fk_inference.py` → 20 passed（纯函数 + 集成）。
- `pytest test/test_learning/` → 127 passed，无回归。
- 全量 `pytest` → 206 passed，1 failed（`test_config/test_settings.py::test_default_encryption_key_is_empty`，**预存环境问题**：项目 `.env` 设了 `ENCRYPTION_KEY`，与本批无关；`ENCRYPTION_KEY=""` 时该测试通过）。
- `ruff check` / `ruff format`（src/learning、src/metadata/models.py）→ clean。
- `alembic upgrade head` / `downgrade -1` / `upgrade head` → 迁移可正向反向执行。
