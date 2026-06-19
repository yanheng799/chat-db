## Parent

PRD：`team-spec/active/2026-06-14-metadata-learning/prd/prd.md`（偏差 C-1 数据外发、偏差 C-2 并发共享 AsyncSession、缺口 C-3 无调用数上限）

## What to build

把 L2 从「静默失效 + 外发原始业务行 + 无成本上限」收紧为「正确、受治理、有成本上限」。三处变更合并为一个 vertical slice：

- **C-1 数据治理**：L2 prompt 改为**只发送结构化信号**（字段名 + 数据类型 + L1 枚举值 + L0 注释 + 拆词结果），**不下发任何原始业务数据行**；移除/改造取样与 prompt 样本块。
- **C-2 并发安全**：`run_l2_inference` 入参改为接收 **session factory**，每个并发任务从 factory 取独立 `AsyncSession`，满足 AsyncSession 单任务安全不变式（修正当前多表并发共享同一 session、失败被编排层 `suppress` 静默吞掉的问题）。
- **C-3 成本上限**：新增 `learning_l2_max_calls` 配置（默认 200，0=不限），单次学习 LLM 调用数达上限时提前停 L2 并记日志。

## Type

AFK（可独立执行，无需人工决策）—— 不发原始行（V1 治理决策）、session factory 修法、`learning_l2_max_calls` 默认 200 均已在 PRD 钉死。

## Acceptance criteria

- [x] Given 一张含未覆盖列的表，When L2 运行，Then 发送给 LLM 的载荷（system + user prompt）只含结构化信号（字段名 / 数据类型 / L1 枚举值 / L0 注释 / 拆词结果），**不含任何原始业务数据行**（对 prompt 载荷做断言）。
- [x] Given 默认并发 5、多张含未覆盖列的表，When L2 运行，Then 每个并发任务使用独立 `AsyncSession`，不触发 AsyncSession 跨任务并发错误，学习日志记录真实 `l2_count`。
- [x] Given LLM 返回某表有效 JSON，When L2 运行，Then 命中列写入 `semantic_description`、`source=llm_inference`、`confidence=0.5`。
- [x] Given LLM 整表返回非法 JSON 或某字段为 null，When L2 运行，Then 该表列保持未覆盖、不抛错、不阻断流水线。
- [x] Given LLM 限流耗尽重试，When L2 运行，Then 该表返回 None、流水线继续。
- [x] Given `learning_l2_max_calls=200` 且待处理表多于上限，When L2 运行，Then 调用数达 200 时提前停 L2、记日志，状态按已覆盖列判定 `success`/`partial_success`。
- [x] Given `learning_l2_max_calls=0`，When L2 运行，Then 不设调用数上限（仅受并发与整体超时约束）。
- [x] L2 并发安全测试走**真实 async session**（不得用共享 mock session 掩盖并发违规）。
- [x] `learning_l2_max_calls` 已加入 `config.settings`（默认 200，0=不限），`.env.example` 同步说明。

## Blocked by

- None - can start immediately

## Notes

- 三处变更共用同一套 L2 测试脚手架（并发>1 真实 session、prompt 载荷断言、达上限提前停），且都改写 L2 处理逻辑，故合为一个 issue（避免拆成 C1/C2/C3 后并行冲突）。
- C-1 后，取样相关代码（`build_sample_query`、prompt 样本块、处理流程内的取样步骤）成为死代码，应移除或改造为只构造结构化信号。
- C-2 改 session factory 后，调用方需相应传入 factory；保持「L2 失败被抑制、不阻断流水线」语义，但失败应记日志（不被静默吞掉）。
- `learning_l2_max_calls` 默认 200 为 PRD 建议值；开放问题 2 待 owner 结合典型 schema 规模最终确认，但不阻塞实现（可后续调默认）。
- **发布顺序**：建议先于或同批于 Issue 002（覆盖率修复）落地，避免覆盖率真实化单独暴露 L2 静默失效。

## Status

ready for PR

## Implementation Notes

- C-1 数据治理：`build_llm_prompt` 改为只接收结构化信号 `FieldSignal`（字段名/数据类型/L1 枚举值/L0 注释/拆词结果）；移除 `build_sample_query`、`truncate_value`、`is_binary_type`、`_BINARY_TYPES`、`MAX_TEXT_LENGTH` 等取样相关代码；system/user prompt 明确要求不依据业务数据行。
- C-2 并发安全：`run_l2_inference` 入参由单个 `AsyncSession` 改为 `session_factory: Callable[[], AsyncSession]`；每个并发任务在 `_process_table` 内 `async with session_factory() as session:` 取独立会话并自行 commit。新增 `config.database.get_session_factory()` 暴露共享工厂；`_run_l2_with_ds` 不再创建目标库 engine / `query_executor`（L2 仅用已提取元数据）。
- C-3 成本上限：新增 `learning_l2_max_calls`（默认 200，0=不限）；用单线程安全的共享计数器在发起新调用前做 `check + increment`（两步之间无 await，原子）；达上限提前停、记日志，状态仍按已覆盖列判定。
- `call_llm_with_retry` 签名同步改为 `(caller, table_name, fields)`。
- 改动文件：`src/learning/l2_inference.py`、`src/learning/orchestrator.py`、`src/config/database.py`、`src/config/settings.py`、`.env.example`；测试 `test/test_learning/conftest.py`（新增共享 `engine`/`session_factory` 夹具）、`test_l2_inference.py`、`test_l2_orchestrator.py`、`test_settings_and_models.py`。

## Acceptance Criteria Coverage

- AC1（只发结构化信号/不发原始行）→ `test_l2_prompt_carries_no_raw_business_data`（orchestrator 捕获真实 prompt 断言）+ `TestBuildLlmPrompt.test_prompt_forbids_using_business_data_rows` / `test_prompt_excludes_arbitrary_raw_values`。
- AC2（默认并发 5、独立 session、真实 l2_count）→ `test_l2_concurrent_tables_use_independent_sessions`（6 表 > 并发 5，全部命中证明无并发错误）。
- AC3（有效 JSON → llm_inference/0.5）→ `test_l2_writes_descriptions_for_uncovered_fields`。
- AC4（非法 JSON/null → 保持未覆盖、不抛错、不阻断）→ `TestParseLlmResponse`（malformed/empty/non-dict 返回 `{}`）+ `test_l2_handles_llm_failure_gracefully`（失败路径不阻断）。
- AC5（限流耗尽 → None、继续）→ `test_all_retries_fail_returns_none` + 上述 graceful failure。
- AC6（达 max_calls 提前停、记日志、状态按已覆盖）→ `test_l2_stops_early_at_max_calls`（max_calls=1 等价机制）。
- AC7（max_calls=0 不限）→ `test_l2_max_calls_zero_means_unlimited`。
- AC8（并发测试走真实 async session）→ `test_l2_concurrent_tables_use_independent_sessions` 使用 `session_factory`（真实 PG）。
- AC9（配置项 + .env）→ `test_default_learning_l2_max_calls` / `test_learning_l2_max_calls_from_env` + `.env.example` 已加 `LEARNING_L2_MAX_CALLS=200`。

## Verification

- `pytest test/test_learning/` → 101 passed（含新增/改写 L2 与 settings 用例），全量通过。
- `ruff check` / `ruff format`（src/learning、src/config）→ clean。
