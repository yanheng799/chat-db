# 错误自愈系统（Phase 7）— 错误分类 + 自动修复 + 重试 + 学习闭环

## 问题陈述

Phase 5/6 遇到 SQL 执行错误直接报错返回用户——表不存在、字段过期、SQL 语法小问题、类型不匹配，这些本该可以自动修复。设计文档核心认知：「表名/字段名错误 99% 来自元数据过期，重点在同步机制」+「每次错误都是学习机会」。Phase 7 让系统从「报错中断」升级为「自动修复→重试→成功」的弹性系统。

## 目标

- SQL 执行失败后自动分类错误类型，按类型触发对应修复策略，修复后重试最多 3 次。
- 元数据过期（表/字段不存在）→ 自动触发 Phase 1 同步 → 重试成功。
- SQL 语法/类型错误 → LLM 多策略重写 → 安全校验 → 重试。
- 跨表缺字段 → 向量库全局搜索 + 图谱 JOIN 路径 → 自动构建 JOIN 查询。
- 成功修复的模式记录到 `healing_records` 表，反馈到元数据/向量库/图谱。

## 非目标

- `JOINS_WITH` 频次实时累加（Phase 11）。
- 跨库字段映射（Phase 10）。
- `healing_records` 的相似错误检索（V1 仅追加，Phase 8+）。

## 用户与场景

1. 查询由于元数据过期失败 → 系统自动同步元数据并重试 → 用户无感知，得到正确结果。
2. SQL 语法错误 → 系统自动 LLM 重写并重试 → 成功则用户无感知，全部失败则告知用户。
3. 字段在目标表中被移除但关联表有 → 系统自动跨表 JOIN 查询 → 返回含 JOIN 的结果。

## 当前状态

- Phase 1 同步引擎已实现（`metadata.sync`）。
- Phase 5 已有安全失败→LLM 重生成一次的单次重试。
- Phase 3 向量检索 + 图谱 JOIN 路径已实现（PR #22）。
- Phase 6 LangGraph 状态图 + DAG 执行器已实现（PR #40）。
- **缺口**：`src/healing/` 为空；无错误分类器、无自愈逻辑、无学习闭环存储。

## 方案描述

Phase 5/6 管道中 SQL 执行失败 → 生成错误事件（原始 SQL + 错误消息 + 查询上下文）→ **自愈 Agent 作为 LangGraph 状态图的条件分支接管** → 分类错误类型：

- `table_not_found` / `column_not_found` → 触发 Phase 1 同步引擎（按表全量同步或全源同步）→ 重试 SQL。
- `sql_syntax_error` → LLM 重写 SQL（附加错误信息）→ 安全校验 → 重试。
- `type_mismatch` → LLM 添加 CAST/转换函数 → 重试。
- `other` → 告知用户 + 记录日志。

跨表字段自愈：`column_not_found` 且普通同步未修复 → 向量库全局搜索候选字段 → 过滤关联表 → 查图谱 JOIN 路径 → 自动构建含 JOIN 的 SQL → 重试。此流程复用 Phase 6 `execute_dag` 编排。

重试最多 3 次，每种策略最多尝试一次（去重）。全部失败→告知用户。自愈 LLM 调用计入 `pipeline_llm_max_calls`。60s 超时→返回「自动修复进行中，请稍后重试」，后台继续自愈。

## 范围

### 范围内

- 7.1 错误分类器（优先用 `pgcode`/`errno` 精确分类，正则兜底）
- 7.2 元数据过期处理（触发同步→重试）
- 7.3 跨表字段自愈（向量+图谱+自动 JOIN，复用 `execute_dag`）
- 7.4 SQL 重写修复（LLM 多策略，最多 3 次，超限降级）
- 7.5 错误学习闭环（PG `healing_records` 表追加记录；元数据/跨表修复反馈到 Phase 3）

### 范围外

- `JOINS_WITH` 频次累加（Phase 11）
- 跨库字段映射（Phase 10）
- `healing_records` 检索/相似匹配（Phase 8+）

## 功能需求

1. 系统必须在 SQL 执行失败后自动分类错误类型（`table_not_found` / `column_not_found` / `sql_syntax_error` / `type_mismatch` / `other`）。
2. 系统必须对元数据过期错误自动触发 Phase 1 同步引擎并重试查询。
3. 系统必须对 SQL 语法/类型错误做 LLM 多策略重写修复并重试（最多 3 次，与元数据同步去重不重复）。
4. 系统必须对跨表缺字段做向量搜索+图谱 JOIN→自动构建含 JOIN 的 SQL→重试。
5. 系统必须在 60s 超时后返回「自动修复进行中，请稍后重试」并后台继续。
6. 系统必须将成功/失败修复记录追加到 `healing_records` 表。
7. 分类器必须优先用数据库错误码（PG `pgcode` / MySQL `errno`）做精确分类，正则仅兜底。
8. 跨表自愈中的 Phase 3 调用必须支持降级（超时→跳过跨表策略→下一策略）。

## 业务规则

- **重试上限**：同一查询最多 3 次修复→重试循环；每种策略最多一次。
- **透明**：不自愈过程逐次打断用户；最终只告知成功或全部失败。
- **超时**：60s 硬超时→返回可理解进度信息 + 后台继续。
- **LLM 调用池**：自愈消耗的 LLM 调用计入 `pipeline_llm_max_calls`。
- **分类优先**：`pgcode`(PG) / `errno`(MySQL) 精确匹配优先于正则。
- **跨表降级**：Phase 3 向量/图谱调用超时→跳过跨表策略→进入下一种策略。

## 边界情况与错误状态

- `other` 类型错误 → 直接告知用户，不自愈。
- 元数据同步本身失败 → 不重试，告知用户。
- 全部 3 次重试失败 → 告知用户，记录 `healing_records` 失败日志。
- 跨表自愈中 Phase 3 不可用 → 跳过跨表策略。
- `healing_records` 表不存在时 → 静默跳过记录（不自愈不阻塞）。

## 数据与状态

- **`healing_records`（新表）**：`error_type, original_sql, fix_type, fix_sql, success, timestamp`。仅追加，V1 不检索。
- **错误事件**（运行期）：`{original_sql, error_message, nl_text, data_source_id, attempt_count}`。

## 发布与运营

- **迁移**：新增 `healing_records` 表的 Alembic 迁移。
- **功能开关**：`SELF_HEALING_ENABLED`（默认 true，可关闭降级为直接报错）。
- **运行时依赖**：Phase 1 同步引擎、Phase 3 向量/图谱、Phase 6 LangGraph+DAG。

## 实现决策

- **模块**：`src/healing/`（classifier.py / metadata_sync.py / cross_table.py / sql_rewrite.py / learning.py）
- **自愈入口**：Phase 6 状态图的条件边路由到 `healing_agent` 子图。
- **跨表编排**：复用 Phase 6 `execute_dag`。
- **分类器优先**：`pgcode`/`errno` 查表分类→消息正则兜底。
- **Phase 3 降级**：调用含超时参数，超时→静默跳过跨表策略。

## 测试决策

- **测外部行为**：各错误类型分类正确→对应策略触发→重试成功/失败。
- **Mock**：Phase 1 同步引擎、Phase 3 向量/图谱、LLM caller、目标库执行器。
- **手工验收**：修改目标库 schema 模拟元数据过期→查询触发自愈→自动同步后重试成功。

## 验收标准

- Given SQL 报 `table not found` → 分类为 `table_not_found` → 触发同步→重试成功。
- Given SQL 语法错误 → LLM 重写→安全校验→重试最多 3 次。
- Given 列不存在且跨表候选命中 → 向量搜索+图谱 JOIN→自动 JOIN→重试成功。
- Given 全部 3 次失败 → 告知用户 + 记录 `healing_records` 失败。
- Given 60s 超时 → 返回进度信息 + 后台继续。

## 开放问题

1. 分类器的 `pgcode`/`errno` 映射表需在实现期填充（postgres/MySQL 官方文档）。
2. `healing_records` 的清理策略（V1 无，Phase 11 补）。

## 补充说明

- **设计基线**：§五 错误自愈、dev plan Phase 7
- **预拆 issue**：A 分类器+元数据过期修复、B SQL 重写修复、C 跨表字段自愈、D 学习闭环+`healing_records`。A→C(依赖 Phase 3/6)→B(独立)→D
