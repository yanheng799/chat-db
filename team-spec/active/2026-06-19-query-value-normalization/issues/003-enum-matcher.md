# 实现枚举值标准化——从口语值经五级策略链映射到数据库实际值

## Parent

PRD：`team-spec/active/2026-06-19-query-value-normalization/prd/prd.md`（4.3 枚举值映射，issue B）

## What to build

实现枚举标准化器：给定 `field_context={table, column, data_source_id}` + `raw_value`（用户口语），按**五级策略链**返回 `NormalizedValue`：
1. 字典表实时查询（查目标库 `information_schema`？V1 查映射中心的枚举别名表即字典）
2. 精确匹配 `display`
3. 别名匹配 `aliases`
4. 编辑距离模糊匹配（阈值 0.7）
5. LLM 兜底（仅结构化信号：字段名 + 已知枚举值列表 + 用户输入；confidence>0.85 采纳）

全失败 → `need_confirm=True`。LLM 兜底与 Phase 2 L2 一致：**不下发原始业务数据行**。

## Type

AFK（可独立执行，无需人工决策）—— 策略链 / 编辑距离阈值 / LLM 治理约束 已在 PRD 钉死。

## Acceptance criteria

- [ ] Given 别名表中 `orders.status` 有 `{value:"completed", display:"已完成", aliases:["完结","结了"]}`，When `raw_value="完结"`，Then `NormalizedValue{db_representation="completed", matched_by="alias", confidence>0}`。
- [ ] Given `raw_value="已完成"`（精确匹配 display），When 标准化，Then `matched_by="display"`。
- [ ] Given `raw_value="己完成"`（编辑距离接近「已完成」），When 标准化，Then 编辑距离≥0.7→匹配到「已完成」→返回 `matched_by="edit_distance"`。
- [ ] Given 前 4 策略均失败且 LLM 兜底返回 valid JSON，When 标准化，Then 写入 `matched_by="llm"`。
- [ ] Given LLM 兜底被调用，When 发送 prompt，Then 内容仅含字段名+已知枚举值列表+用户输入，**不含任何原始业务数据行**（对 prompt 做断言）。
- [ ] Given LLM 兜底也失败或 confidence<0.85，When 标准化，Then `need_confirm=True, db_representation=None, confidence=0`。
- [ ] Given 无 LLM API key 或 LLM 超时，When 标准化，Then 跳过 strategy 5（不抛错）、返回 need_confirm。
- [ ] 相关单测覆盖所有策略（mock LLM 调用 + mock 外部服务）。

## Blocked by

- #2（需映射中心的枚举别名表 + CRUD 做策略 1）

## Notes

- LLM 兜底复用现有 `llm/client.py`（create_llm_caller），治理与 Phase 2 L2 一致。
- 编辑距离用 `difflib.SequenceMatcher`（stdlib）。
- 策略链每步命中即停；多候选等距且难区分 → need_confirm。

## Publish Status

- Status: created
- Updated At: 2026-06-19T06:20:48Z
- GitHub Number: 25
- GitHub URL: https://github.com/yanheng799/chat-db/issues/25
