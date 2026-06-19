# 多表联合查询 (Multi-Table JOIN)

## 问题陈述

当前 Chat-DB 的 SQL 安全校验硬禁止所有 JOIN 和多表查询。用户提问"设计交底文件包含哪些 chunk"时，LLM 生成了正确的 JOIN SQL，但被拦截。用户只能拆成多次单表查询，体验割裂。

## 目标

- 允许生成并执行至多涉及 3 张表的 JOIN 查询
- 利用知识图谱中的 FK 和推断关系指导 LLM 生成正确 ON 条件
- 保持只读安全约束（黑名单、LIMIT、禁止 SELECT *）

## 非目标

- 子查询、UNION、CTE、窗口函数
- 3 表以上的 JOIN
- 语义匹配层改动
- 图谱可视化（D3.js）

## 用户与场景

1. 作为查询用户，我问"设计交底文件包含哪些 chunk"，系统自动 JOIN `rag_documents` 和 `rag_chunks`，返回关联结果。
2. 作为查询用户，我问"每个数据集有多少文档"，系统 JOIN `rag_datasets` 和 `rag_documents`，返回统计结果。

## 当前状态

- **安全校验**：`validate_sql` 硬禁止 JOIN 和多 FROM（46-49 行）
- **SQL 生成器**：prompt 中写"只查询单张表（不要写 JOIN）"
- **图谱查询**：`shortest_join_path` 已就绪，可查两张表之间的 JOIN 路径
- **管线**：`run_single_step` 在安全校验失败时已支持 LLM 重试

## 方案描述

1. 语义匹配照常返回字段（可能跨表）
2. 管线从 matches 中提取涉及的表名集合
3. 对每对表调用 `shortest_join_path` 查图谱，获取 JOIN 路径列表
4. 去重后格式化注入 SQL 生成 prompt
5. LLM 根据表结构 + JOIN 路径生成 SQL
6. 安全校验：允许 JOIN（≤2 个），禁止子查询/UNION/CTE
7. 执行并返回结果

### 安全边界

| 检查项 | 规则 |
|--------|------|
| 黑名单 | INSERT/UPDATE/DELETE/DROP/TRUNCATE/ALTER/EXEC/INTO OUTFILE/LOAD DATA/SLEEP/BENCHMARK/@@ |
| JOIN 上限 | 最多 2 个 JOIN 关键字（涉及 ≤3 张表） |
| 子查询 | 禁止（括号内含 SELECT） |
| UNION/CTE | 禁止 |
| LIMIT | 必须有，且 ≤ 1000 |
| SELECT * | 禁止 |

## 功能需求

1. 安全校验允许包含 ≤2 个 JOIN 的 SELECT 语句通过
2. 安全校验拒绝子查询、UNION、CTE
3. SQL 生成器 prompt 允许 JOIN，并包含图谱提供的 JOIN 路径
4. 管线在 SQL 生成前自动查询图谱获取 JOIN 路径
5. Neo4j 不可用时，降级为 LLM 凭表结构自行推断 JOIN 条件
6. 非 JOIN 的单表查询行为不变（回归）

## 业务规则

- 所有 JOIN 查询必须包含 LIMIT ≤ 1000
- JOIN 路径优先使用 REFERENCES（FK），其次 INFERRED_REF（推断），confidence < 0.5 的路径不注入 prompt
- 安全校验不检查 ON 条件的语义正确性（依赖 LLM）

## 边界情况与错误状态

- **图谱中无 JOIN 路径**：prompt 不注入路径，LLM 凭表结构推断 → 可能写错 ON 条件 → 结果显示错误/空
- **LLM 生成超过 2 个 JOIN**：安全校验拒绝，返回错误信息
- **LLM 生成子查询**：安全校验拒绝
- **JOIN 查询超时**：同现有单表超时处理（30s）
- **Neo4j 连接失败**：降级为纯 LLM，日志 warning

## 实现决策

| 模块 | 文件 | 变更 |
|------|------|------|
| 安全校验 | `sql/security.py` | 移除单表限制；新增 JOIN 计数、子查询检测、UNION/CTE 黑名单 |
| SQL 生成器 | `sql/generator.py` | 移除"只查单表"约束；新增 `join_paths` 参数；prompt 新增 JOIN 路径段落 |
| 管线 | `pipeline/single_step.py` | SQL 生成前新增图谱查询步骤 |
| 图谱查询 | `knowledge/graph_query.py` | 复用已有 `shortest_join_path`（无需修改） |

## 测试决策

- **安全校验**：单元测试覆盖合法 JOIN 通过、超限 JOIN 拒绝、子查询拒绝、UNION 拒绝
- **管线**：集成测试验证 JOIN 路径注入 prompt、结果正确返回
- **手工验收**：5-10 条跨表查询（如"每个数据集的文档数""设计交底文件包含的 chunk"）

## 验收标准

- [ ] Given 查询"每个数据集有多少文档"，When 执行，Then 返回 JOIN `rag_datasets` 和 `rag_documents` 的统计结果
- [ ] Given 查询"设计交底文件包含哪些 chunk"，When 执行，Then 返回 JOIN `rag_documents` 和 `rag_chunks` 的关联结果
- [ ] Given JOIN 查询涉及 4 张表，When 安全校验，Then 拒绝并返回错误原因
- [ ] Given 查询含子查询 `SELECT * FROM (SELECT ...)`，When 安全校验，Then 拒绝
- [ ] Given 查询含 UNION，When 安全校验，Then 拒绝
- [ ] Given 原单表查询"统计文档总数"，When 执行，Then 行为与改前一致（回归）

## 开放问题

- 无

## 补充说明

- 依赖：知识图谱已在 Neo4j 中构建（同步→学习→刷新知识库）
- 依赖：`shortest_join_path` 已在 `knowledge/graph_query.py` 中实现
- 降级：Neo4j 不可用时 LLM 自行推断 JOIN
