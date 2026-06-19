# 串联语义匹配、值标准化、SQL 生成、安全校验与执行为完整单步查询

## Parent

PRD：`team-spec/active/2026-06-19-semantic-matching-pipeline/prd/prd.md`（5.5 单步查询完整串联，issue F）

## What to build

实现单步查询管道编排器：接收自然语言输入 → 按管道顺序编排全部模块（时间前置提取→语义匹配→值标准化→SQL 生成→安全校验→审核阻断→SQL 执行→结果总结）。含 LLM 调用管控（`pipeline_llm_max_calls` 默认 5，超限降级）、审核阻断（收集 LLM 兜底匹配 + Phase 4 need_confirm 项合并批量用户确认）、管道异常传播（不可恢复→终止+报错；可恢复→降级继续）、结果总结（仅聚合查询结果过 LLM 做自然语言包装；行级直接返表）。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given `"查一下昨天的订单总数"`（mock LLM + mock 目标库），When 管道运行，Then 管道按顺序调用各模块、返回正确 Count 结果。
- [ ] Given 语义匹配 LLM 兜底 `need_confirm=True` + Phase 4 标准化器 `need_confirm=True`，When 管道运行，Then 合并所有 need_confirm 项、一次性返回追问（不逐条打断）。
- [ ] Given 安全校验失败，When 管道运行，Then 告知用户原因 + LLM 重生成一次 → 再失败→最终阻断、不执行 SQL。
- [ ] Given `pipeline_llm_max_calls=3` 且 LLM 调用达 3 次，When 管道运行，Then 后续 LLM 步骤降级（如跳结果总结、直接返表）。
- [ ] Given 聚合查询结果，When 总结，Then 未超 LLM 调用上限时 LLM 做自然语言包装；超限→直接返表。
- [ ] Given 行级查询结果，When 总结，Then 直接返表（不经过 LLM）。
- [ ] Given 向量检索超时，When 管道运行，Then 降级跳过向量、直接走 LLM 兜底（不可恢复步骤才终止）。
- [ ] 相关集成测试（mock LLM + mock 目标库）覆盖正常路径、need_confirm 路径、安全拦截路径、LLM 超限降级路径。

## Blocked by

- #2（语义匹配器）、#3（SQL 生成器）、#4（安全校验）、#5（SQL 执行器）

## Notes

- 管道编排器是 `src/pipeline/single_step.py`。
- LLM 调用计数器：每次 LLM 调用前检查 `pipeline_llm_max_calls`，达上限→跳过该步骤的 LLM 部分并降级。
- 结果总结治理：与 Phase 2 L2 一致（聚合值可发给 LLM 做总结；行级数据不发送、直接返表）。
- 端到端验收需真实 LLM + 目标库，实现期 mock 可覆盖全场景。

## Publish Status

- Status: created
- Updated At: 2026-06-19T06:59:53Z
- GitHub Number: 35
- GitHub URL: https://github.com/yanheng799/chat-db/issues/35
