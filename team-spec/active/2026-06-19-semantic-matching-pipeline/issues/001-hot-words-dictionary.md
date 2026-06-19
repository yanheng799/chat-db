# 构建 V1 热词词典与行业词库种子数据供语义匹配第一层加速

## Parent

PRD：`team-spec/active/2026-06-19-semantic-matching-pipeline/prd/prd.md`（3.4 热词词典收编，issue A）

## What to build

构建 V1 热词词典与行业词库的**内存种子数据**（Python 字典常量），作为语义匹配四层递进的第一层确定性加速。热词：10–15 条常见电商/ERP 术语→字段/聚合映射（含 2–3 条锁定业务指标公式模板，`locked=true`）。行业词库：5–10 条领域术语→热词翻译（如「GMV→销售额」）。V1 无 CRUD UI，管理员通过编辑代码/配置文件维护。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [x] V1 热词覆盖 13 条（销售额/订单数/客单价/库存量/毛利率 等）+ 行业词 7 条。
- [x] 锁定公式 `locked=True` 标记（销售额、毛利率、客单价）。
- [x] 数据结构为 Python 字典常量，无 DB/迁移依赖。

## Blocked by

- None - can start immediately

## Notes

- 热词字典为 Python 常量文件（如 `src/semantic/hot_words.py`），代码内直接定义。
- 锁定公式（`locked=True`）禁止 LLM 动态编造；Phase 6 多步查询可引用。
- Phase 10 才会做热词/行业的 CRUD UI 管理端；V1 编辑靠改代码/配置文件。

## Publish Status

- Status: created
- Updated At: 2026-06-19T06:59:40Z
- GitHub Number: 30
- GitHub URL: https://github.com/yanheng799/chat-db/issues/30
