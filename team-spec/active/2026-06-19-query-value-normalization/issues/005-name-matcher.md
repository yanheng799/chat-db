# 实现名称简称匹配——七级策略递进加 LIKE 回退

## Parent

PRD：`team-spec/active/2026-06-19-query-value-normalization/prd/prd.md`（4.5 名称简称匹配，issue D）

## What to build

实现名称标准化器：七级策略递进（精确匹配→简称→别名→拼音→关键字→编辑距离≥0.7→向量语义）把用户口语中的实体简称映射为数据库里的全称。全策略失败 → 回退到目标业务库 `SELECT DISTINCT col FROM table WHERE col LIKE '%xxx%' LIMIT 10`（复用 `query_executor`）；仍失败 → `need_confirm=True`。LIKE 回退目标库时只读、限流、超时（沿用 Phase 2 安全约束）。

## Type

AFK（可独立执行，无需人工决策）—— 7 策略顺序 / 编辑距离阈值 / LIKE 回退参数 已在 PRD 钉死。

## Acceptance criteria

- [ ] Given 别名表中有 `{short_name:"华为", full_name:"Huawei Technologies"}`，When `raw_value="华为"`，Then `NormalizedValue{db_representation="Huawei Technologies", matched_by="short_name"}`。
- [ ] Given `raw_value="HW"` 且别名表有 `{aliases:["HW"]}`，When 标准化，Then `matched_by="alias"`。
- [ ] Given 拼音匹配「huawei」→「华为」，When 标准化，Then `matched_by="pinyin"`。
- [ ] Given 前 6 策略均失败且向量语义命中，When 标准化，Then `matched_by="vector"`。
- [ ] Given 全部 7 策略失败，When 标准化，Then 发起目标库 `SELECT DISTINCT col FROM table WHERE col LIKE '%xxx%' LIMIT 10`；结果非空→返回 alternatives 供用户选择；结果为空→need_confirm。
- [ ] Given 目标库不可达，When LIKE 回退，Then 静默跳过 LIKE（不抛错）、返回 need_confirm。
- [ ] 名称标准化器按 field_context 关联对应 `column`（可选指定 `target_table`，未指定则全局匹配该源的名称简称表）。
- [ ] 相关单测覆盖前 6 策略（纯文本）+ mock 向量检索 + mock LIKE 回退，LIKE 回退 SQL 含 `LIMIT 10` 与只读约束。

## Blocked by

- #2（需映射中心的名称简称表 + CRUD 做策略查找）

## Notes

- 向量语义（strategy 7）可选依赖 Phase 3 `field_descriptions` 向量检索；Phase 3 未落地时先 mock 或跳过（不影响其他策略）。
- LIKE 回退复用 Phase 2 `query_executor` 抽象，`LIMIT 10`；超时复用 `statement_timeout`。
- 拼音匹配用 `pypinyin`（需新增依赖）；关键字匹配用分词后子串。
- 编辑距离阈值 0.7，用 `difflib.SequenceMatcher`。

## Publish Status

- Status: created
- Updated At: 2026-06-19T06:20:52Z
- GitHub Number: 27
- GitHub URL: https://github.com/yanheng799/chat-db/issues/27
