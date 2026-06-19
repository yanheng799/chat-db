# 支持多表 JOIN 查询——安全校验放开 + 图谱路径注入

## Parent

PRD：`team-spec/active/2026-06-20-multi-table-join/prd/prd.md`

## What to build

移除 SQL 安全校验中的单表硬限制，允许生成并执行至多涉及 3 张表的 JOIN 查询。利用知识图谱中的 FK 关系和 L2 推断关联，在 SQL 生成 prompt 中注入表间 JOIN 路径，指导 LLM 写出正确的 ON 条件。

端到端行为：用户提问"每个数据集有多少文档"→ 语义匹配返回 `rag_datasets` 和 `rag_documents` 字段 → 管线查图谱获取 JOIN 路径 → LLM 生成 `SELECT ... FROM rag_datasets JOIN rag_documents ON ... LIMIT 1000` → 安全校验通过 → 执行 → 返回结果。

改动范围：

1. `sql/security.py`：移除单表限制（46-49 行）；新增 JOIN 计数 ≤ 2、子查询检测、UNION/CTE 检测
2. `sql/generator.py`：移除 prompt 中"只查单表"约束；新增 `join_paths` 参数；prompt 新增"可用的 JOIN 路径"段落
3. `pipeline/single_step.py`：SQL 生成前新增图谱查询步骤（从 matches 提取表名集合 → 两两查 `shortest_join_path` → 去重 → 传入 `generate_sql`）
4. `knowledge/graph_query.py`：复用已有 `shortest_join_path`（无需修改）

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given 查询"每个数据集有多少文档"，When 执行，Then 返回 JOIN `rag_datasets` 和 `rag_documents` 的统计结果
- [ ] Given 查询含 3 张表的 JOIN，When 安全校验，Then 通过（2 个 JOIN 关键字）
- [ ] Given 查询含 4 张表的 JOIN（3 个 JOIN 关键字），When 安全校验，Then 拒绝并返回 `multi-table query exceeds limit (max 2 JOINs)`
- [ ] Given 查询含子查询 `SELECT * FROM (SELECT ...)`，When 安全校验，Then 拒绝
- [ ] Given 普通单表查询，When 执行，Then 行为不变（回归）
- [ ] Given 图谱有 `rag_datasets ← rag_documents` 的 FK 路径，When SQL 生成，Then prompt 包含该 JOIN 路径
- [ ] Given 图谱不可用（Neo4j 未启动），When SQL 生成，Then 降级为 LLM 自行推断 JOIN

## Blocked by

- None

## Notes

- 安全边界：最多 2 个 JOIN（涉及 ≤3 张表）、禁止子查询（括号内含 SELECT）、禁止 UNION/CTE
- 黑名单、LIMIT ≤ 1000、禁止 SELECT * 保持不变
- 图谱路径仅在 confidence ≥ 0.5 时注入 prompt
- 建议实现后手工验证 5-10 条 JOIN 查询的 ON 条件正确性

## Status

implemented

## Implementation Notes

### 安全校验 (`sql/security.py`)
- 移除单表硬限制（原 46-49 行）
- 新增 `_MAX_JOINS = 2`：JOIN 关键字计数 ≤ 2
- 新增 `_SUBQUERY_PATTERN`：检测括号内 SELECT
- 新增 `_UNION_CTE_PATTERN`：检测 UNION/WITH AS

### SQL 生成器 (`sql/generator.py`)
- Prompt 移除"只查询单张表"约束，改为"最多 JOIN 2 张额外表"
- 新增 `join_paths` 参数
- Prompt 新增"可用的 JOIN 路径"段落（或"无路径可自行推断"）

### 管线 (`pipeline/single_step.py`)
- SQL 生成前新增图谱查询步骤：
  - 从 matches 提取表名集合
  - 对每对表调用 `shortest_join_path`（confidence ≥ 0.5）
  - 传入 `generate_sql(..., join_paths=...)`
- Neo4j 不可用时静默降级

### 验证
- 安全校验 7 个场景全部正确（单表/JOIN 2/JOIN 3/JOIN 4/子查询/UNION/CTE）
- 完整管线测试：`每个数据集有多少文档` → LEFT JOIN → 2 cols × 3 rows
- Backend tests: 68/69 passed (1 pre-existing unrelated)
- Frontend build: all routes OK
