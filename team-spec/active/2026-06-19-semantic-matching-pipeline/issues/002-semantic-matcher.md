# 实现四层递进语义匹配——把用户口语映射到表.列

## Parent

PRD：`team-spec/active/2026-06-19-semantic-matching-pipeline/prd/prd.md`（5.1 四层语义匹配，issue B）

## What to build

实现四层递进语义匹配器：给定用户原文 + `data_source_id`，逐层匹配每个用户术语到具体的表.列：
1. **热词词典**（确定性，来自 #1）
2. **行业词库**（领域术语翻译，来自 #1）
3. **向量检索**（Phase 3 `search_fields`，语义相似度 top-k）
4. **LLM 兜底**（仅结构化信号：字段名+描述；`source=llm_fallback`，`need_confirm=True`）

每层命中即停、不继续下层。LLM 兜底仅用结构化信号、不下发原始业务数据行（与 Phase 2 L2 治理一致）。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given 热词词典有 `"销售额"→orders(SUM(price*quantity))`，When `raw_text="销售额"`，Then `matched_by="hot_word"`、`need_confirm=False`。
- [ ] Given 行业词库有 `"GMV"→"销售额"`，When `raw_text="GMV"`，Then 先翻译为「销售额」再命中热词、`matched_by="industry"`。
- [ ] Given 前两层未命中且向量检索返回 `orders.status` 相似度高于阈值，When 匹配，Then `matched_by="vector"`。
- [ ] Given 前三层均失败且 LLM 兜底返回有效匹配，When 匹配，Then `matched_by="llm_fallback"`、`need_confirm=True`。
- [ ] Given LLM 兜底被调用，When 发送 prompt，Then 内容仅含字段名+语义描述+用户原文，**不含原始业务数据行**。
- [ ] Given 全四层失败，When 匹配，Then 返回空匹配列表，管道告知用户无法理解。
- [ ] 向量检索可降级（Phase 3 不可用时跳过第 3 层、直接走 LLM）。

## Blocked by

- #1（需热词词典 + 行业词库）

## Notes

- 向量检索调 Phase 3 `search_fields(query, data_source_id, top_k)`。
- LLM 兜底复用 `llm/client.py`；system prompt 只含字段元数据（表.列 + 语义描述）。
- 测试可 mock LLM、mock Phase 3 向量检索、mock 热词。

## Publish Status

- Status: created
- Updated At: 2026-06-19T06:59:43Z
- GitHub Number: 31
- GitHub URL: https://github.com/yanheng799/chat-db/issues/31
