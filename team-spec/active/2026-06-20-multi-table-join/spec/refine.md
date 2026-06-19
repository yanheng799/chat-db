# 多表联合查询 (Multi-Table JOIN)

## 需求摘要

移除 SQL 安全校验中的单表硬限制，允许 Chat-DB 生成并执行带 JOIN 的只读查询。利用知识图谱中的 FK 关系和 L2 推断关联，指导 LLM 生成正确的 JOIN 条件。

## 规范术语

| 术语 | 定义 |
|------|------|
| JOIN 路径 | 知识图谱中两个表之间的连接链，由 FK 关系（REFERENCES）或推断关系（INFERRED_REF）组成 |
| 连通子图 | 语义匹配涉及的多张表在知识图谱中的可达关系集合 |
| 复杂度上限 | 单条 SQL 最多涉及 3 张表（即最多 2 个 JOIN 关键字），禁止子查询 / UNION / CTE |

## 范围内

- SQL 安全校验放开 JOIN 和多个 FROM 子句
- SQL 生成器 prompt 允许 JOIN，并注入图谱 JOIN 路径
- 利用 `shortest_join_path` 为语义匹配涉及的表预计算 JOIN 路径
- 安全边界：最多涉及 3 张表（最多 2 个 JOIN）、禁止子查询/UNION/CTE、必须有 LIMIT、禁止 SELECT *、保持黑名单
- 管线在语义匹配后、SQL 生成前，查询图谱获取 JOIN 路径并注入 prompt

## 范围外

- 子查询、UNION、CTE、窗口函数
- 3 表以上的 JOIN
- 语义匹配层改动（保持现有匹配逻辑）
- D3.js 知识图谱可视化（V2）
- 查询结果跨多步分解执行（multi-step pipeline）

## 关键决策

1. **安全边界**：最多 JOIN 3 张表，禁止子查询/UNION/CTE，保留现有黑名单+LIMIT+禁止 SELECT *
2. **JOIN 路径来源**：知识图谱 `shortest_join_path`（Neo4j FK + L2 推断）
3. **语义匹配**：不动，SQL 生成器负责多表编排
4. **路径注入方式**：遍历 matched fields 涉及的表，两两查 `shortest_join_path`，去重后格式化注入 prompt

## 实现要点

### 安全校验 (`sql/security.py`)
- 移除 46-49 行的单表硬限制
- 新增：JOIN 表数 ≤ 3（正则匹配 JOIN 关键字计数）
- 新增：禁止子查询（正则匹配括号中含 SELECT）
- 新增：禁止 UNION / CTE（黑名单扩展）

### SQL 生成器 (`sql/generator.py`)
- Prompt 移除"只查询单张表"
- 新增 `join_paths` 参数：`[{from_table, from_column, to_table, to_column, type, confidence}]`
- Prompt 新增段落："可用的 JOIN 路径: ..."

### 管线 (`pipeline/single_step.py`)
- 步骤 5 (SQL 生成) 前新增步骤：
  - 从 matches 中提取涉及的表名集合
  - 对每对表调用 `shortest_join_path`
  - 去重后传入 `generate_sql(..., join_paths=...)`

### 图谱查询 (`knowledge/graph_query.py`)
- 复用已有 `shortest_join_path` 函数（无需修改）

## 开放问题

- 无

## 轻量风险

- **P1**：LLM 可能在有 JOIN 路径时仍写出错误的 ON 条件 → 安全校验无法检测语义错误 → 依赖 LLM 能力，建议先在测试环境验证 JOIN 准确率
- **P2**：Neo4j 不可用时 JOIN 路径为空 → LLM 退化为自己猜 → 降级方案：无路径时 prompt 中不注入，LLM 凭表结构推断

## Change Log

- 2026-06-20：初始细化。确认安全边界、JOIN 路径来源、语义匹配不改、路径注入方式。
