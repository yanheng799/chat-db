# 实现区域/地名标准化——粒度自适应匹配并展开为 SQL IN

## Parent

PRD：`team-spec/active/2026-06-19-query-value-normalization/prd/prd.md`（4.4 区域/地名处理，issue C）

## What to build

实现区域标准化器：把用户口语中的地名表述（「华东」「上海」「浦东」）按**粒度自适应**匹配到区域字典（省/市/区/自定义），并做**层级包含展开**——如「华东」展开为其下属省/市/区 → SQL `IN (...)`。匹配按名称+别名，不匹配 → `need_confirm=True`。区域字典由 #2 提供与管理。

## Type

AFK（可独立执行，无需人工决策）—— 粒度级别 / 层级展开规则 已在 PRD 钉死。

## Acceptance criteria

- [ ] Given 区域字典中有 `{name:"上海", level:"city"}`，When `raw_value="上海"`，Then `NormalizedValue{db_representation="city IN ('上海')", matched_by="name"}`。
- [ ] Given `raw_value="华东"` 且区域字典有 `华东`(level=custom)及其下属省市，When 标准化，Then 层级展开为下属城市列表 → `db_representation=city IN ('上海','南京','杭州',...)`。
- [ ] Given `raw_value="浦东"`，When 标准化，Then `matched_by="name"`, `db_representation` 精确包含浦东（不错误展开）。
- [ ] Given `raw_value="未知城市"` 不在区域字典，When 标准化，Then `need_confirm=True, db_representation=None`。
- [ ] Given 查询的是 `level=custom` 的自定义大区，When 层级展开，Then 递归收集所有下属叶子（省/市/区），返回 SQL IN。
- [ ] 相关单测覆盖省/市/区/自定义各级匹配 + 层级展开为空/有子/无子的边界。

## Blocked by

- #2（需区域字典表 + 种子数据）

## Notes

- 区域 CSV 种子（#2 负责导入）提供 V1 预置数据。本 issue 只读区域字典做匹配。
- 粒度自适应判定：输入长度/别名匹配到哪个 level 即返回哪个 level；多 candidate 时优先匹配更精确的。
- 层级展开前确保字典不包含循环引用（parent_code 成环）；V1 假设数据合法。

## Publish Status

- Status: created
- Updated At: 2026-06-19T06:20:50Z
- GitHub Number: 26
- GitHub URL: https://github.com/yanheng799/chat-db/issues/26
