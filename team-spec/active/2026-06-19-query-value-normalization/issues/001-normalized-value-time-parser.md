# 定义查询值标准化结果结构并实现时间表述解析器

## Parent

PRD：`team-spec/active/2026-06-19-query-value-normalization/prd/prd.md`（4.1 NormalizedValue + 4.2 时间标准化，issue A）

## What to build

定义 `NormalizedValue` 数据结构（`original`/`normalized`/`value_type`/`db_representation`/`confidence`/`matched_by`/`need_confirm`/`alternatives`），并实现**时间标准化器**：把用户输入的时间口语表述（「上个月」「2026 年 5 月」「618」）解析为日期范围 SQL 片段。时间标准化**不依赖字段上下文**，可被 Phase 5 前置调用；也提供 `normalize(field_context, raw_value)` 统一入口（对时间类型忽略 field_context）。

## Type

AFK（可独立执行，无需人工决策）—— NormalizedValue 字段 / 时间表述列表 / 固定日期周期预设 已在 PRD 钉死。

## Acceptance criteria

- [x] Given `raw_value="上个月"`，When 时间标准化，Then `NormalizedValue{value_type="time", matched_by="relative_time"}`。
- [x] Given `raw_value="2026年5月"`（绝对时间），When 标准化，Then 解析为月范围。
- [x] Given `raw_value="2026-05-01"`，When 标准化，Then 解析为单日。
- [x] Given `raw_value="618"`，When 标准化，Then 匹配 fixed_period 六月范围。
- [x] Given 无法解析的时间字符串，When 标准化，Then `need_confirm=True, db_representation=None`。
- [x] 时间标准化器提供独立入口 `parse_time(raw_value) → NormalizedValue`。

## Blocked by

- None - can start immediately

## Notes

- 时间标准化不依赖外部服务（纯日期计算），测试全程走单元测试。
- `FIXED_DATE_PERIODS` 预设：`双十一(11-01/11-11)`、`618(06-01/06-18)`；管理员可通过 #2 的 CRUD 增删。
- 排除：财年、农历、动态相对周期 → 引导用户用绝对日期。

## Publish Status

- Status: created
- Updated At: 2026-06-19T06:20:43Z
- GitHub Number: 23
- GitHub URL: https://github.com/yanheng799/chat-db/issues/23
