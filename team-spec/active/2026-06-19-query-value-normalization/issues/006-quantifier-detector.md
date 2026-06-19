# 实现模糊量词检测——检测口语量词并返回追问而不自动量化

## Parent

PRD：`team-spec/active/2026-06-19-query-value-normalization/prd/prd.md`（4.6 数值范围处理，issue E）

## What to build

实现数值标准化器：检测用户口语中是否包含**模糊量词**（高价值/大额/小额/适中/大量/少量），若检测到 → 返回 `NormalizedValue{need_confirm=True, value_type="quantifier"}`，让 Phase 6 向用户追问（如「您定义的'大额'是多少？请提供具体数值。」）。**不自动量化**（不猜测阈值）。

## Type

AFK（可独立执行，无需人工决策）—— 量词列表 / 追问行为 / 不自动量化 已在 PRD 钉死。

## Acceptance criteria

- [x] Given `raw_value="大额"`，When 数值标准化，Then `need_confirm=True, value_type="quantifier"`。
- [x] Given `raw_value="大额订单"`（复合短语），When 标准化，Then `need_confirm=True`（子串检测）。
- [x] Given `raw_value="1000元"`（具体数值），When 标准化，Then `need_confirm=False`（不误判）。
- [x] 全部预定义量词（6 个）均可检测；精确数值 + 空字符串不误判。

## Blocked by

- None - can start immediately

## Notes

- 量词检测用纯文本匹配（正则/子串），不依赖外部服务。
- 预定义量词初始集：`高价值/大额/小额/适中/大量/少量/昨天`？——`昨天`是时间，由 #1 处理。量词仅限数值模糊词。
- `NormalizedValue` 的 `alternatives` 在量词场景可空（无候选值可提供）。

## Publish Status

- Status: created
- Updated At: 2026-06-19T06:20:55Z
- GitHub Number: 28
- GitHub URL: https://github.com/yanheng799/chat-db/issues/28
