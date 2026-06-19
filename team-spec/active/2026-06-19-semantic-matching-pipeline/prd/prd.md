# 语义匹配 + 单步查询核心链路（Phase 5）— 首次可演示里程碑

## 问题陈述

Phase 1-4 各自建了能力——元数据提取与学习、知识库（向量+图谱）、值标准化——但还没有一条链路把它们串成实际可用的查询。目前系统无法接收自然语言输入、无法返回查询结果。Phase 5 把这些能力串联成**首个端到端 NL→SQL→结果**的可演示闭环，是整个系统从「基建」到「可用」的转折点。

## 目标

- 用户输入「查一下昨天的订单总数」，系统从语义匹配到 SQL 执行到结果总结全自动跑通，返回正确答案（≤30 秒）。
- 语义匹配经四层递进（热词→行业词→向量→LLM）识别字段；LLM 兜底结果与未解值合并做一次用户确认。
- 生成单步只读 SQL，经安全校验（黑/白名单+语法）后执行；安全失败时告知用户并尝试 LLM 重生成一次。
- V1 构建延迟的 3.4 热词词典（小规模精选种子，无 CRUD UI），作为语义匹配第 1 层确定性加速。

## 非目标

- 多步查询路由 / 多 Agent 编排（Phase 6 LangGraph）。
- 错误自愈（元数据过期自动重试）—— Phase 7。
- 管理端审核策略配置 UI / 审核仪表盘 / 热词 CRUD UI（Phase 10）。
- Chat UI 前端（Phase 10）。
- 查询历史、结果缓存、用户画像（Phase 11/用户特征系统）。

## 用户与场景

1. 作为**查询用户**，我说「查一下昨天的订单总数」，系统端到端返回「昨天共有 128 笔订单」。
2. 作为**查询用户**，我说「上个月已完成的大额订单有哪些」，系统匹配字段、标准化时间和枚举值、检测「大额」→ 合并 LLM 兜底结果 + need_confirm 项→ 一次向我展示确认 → 确认后执行。
3. 作为**查询用户**，当语义匹配所有策略都失败时，系统告知我无法理解查询、建议换种问法。
4. 作为**查询用户**，当生成的 SQL 未通过安全校验时，系统告知我原因并尝试自动修正后重新执行。

## 当前状态

- **Phase 1**：元数据提取（PG/MySQL schema → app DB）。完成。
- **Phase 2**：元数据学习（`semantic_description` + 推断外键 `metadata_inferred_fks`）。完成（PR #17）。
- **Phase 3**：知识库（Milvus `field_descriptions` 向量 + Neo4j 图谱 + 最短路径查询 + 生命周期刷新）。完成（PR #22）。
- **Phase 4**：值标准化器（时间/枚举/区域/名称/量词 + 值映射中心 CRUD + 3 张表迁移）。完成（PR #29）。
- **缺口**：`src/semantic/` 和 `src/sql/` 为空；`src/pipeline/` 为空；3.4 热词词典不存在。Phase 5 需从零建语义匹配器、SQL 生成器、安全校验器、SQL 执行器、单步流水线编排器。

## 方案描述

**主路径**：用户输入自然语言 → **时间前置提取**（Phase 4 `parse_time`） → **语义匹配**（四层递进识别每个用户术语对应的表.列：热词词典 → 行业词库 → Phase 3 向量检索 `field_descriptions` → LLM 兜底，`source=llm_fallback` 触发 `need_confirm=True`） → **值标准化**（对每个已识别字段调 Phase 4 标准化器做枚举/区域/名称标准化；量词检测） → **SQL 生成**（LLM prompt 注入 schema 上下文 + 标准化值 + 匹配结果，约束只读/LIMIT/禁止 SELECT *） → **安全校验**（黑名单+白名单+语法；失败则告知用户原因 + LLM 重生成一次 → 再失败则阻断） → **审核阻断**（收集所有 `need_confirm=True` 的项——含 LLM 兜底匹配 + Phase 4 未解值 + 量词——**一次性批量展示给用户确认**；用户确认后继续，拒绝则返回修正） → **SQL 执行**（只读连接 + `statement_timeout` + 结果捕获） → **结果总结**（仅对聚合查询结果做 LLM 自然语言包装；行级查询返回表格、不经过 LLM）。

**管道异常传播**：任一不可恢复步骤失败 → 终止并返回友好错误（如目标库不可达）；可恢复步骤失败（如向量检索超时） → 降级继续（跳过向量检索、直接走 LLM 兜底）。

**LLM 调用管控**：单次查询 LLM 调用上限 `pipeline_llm_max_calls`（默认 5），超限降级（如跳结果总结、直接返回表格）。

## 范围

### 范围内

- **3.4 热词词典**（收编）：10–15 条精选热词→字段/聚合映射 + 2–3 条锁定业务指标公式模板 + 5–10 条行业术语，V1 无 CRUD UI（代码/配置维护）。
- **5.1 四层语义匹配**：热词→行业词→向量检索（Phase 3 `field_descriptions`）→ LLM 兜底（`source=llm_fallback`，`need_confirm=True`）。
- **5.2 单步 SQL 生成**：LLM 生成 post-标准化单表查询 SQL。
- **5.3 安全校验**：黑名单+白名单+`sqlparse` 语法校验；失败→告知用户+LLM 重生成一次。
- **5.4 SQL 执行**：只读连接+超时+结果捕获。
- **5.5 单步查询串联**：编排全链路 + 审核阻断 + LLM 调用管控。

### 范围外

- 多步查询 / 多 Agent 编排（Phase 6 LangGraph）。
- 错误自愈（Phase 7）。
- 管理端 UI（审核策略配置/审核仪表盘/热词 CRUD）—— Phase 10。
- Chat UI 前端（Phase 10）。
- 查询历史/结果缓存/用户画像（Phase 11）。

## 功能需求

1. 系统必须提供单步查询入口，接收自然语言输入，返回结构化结果或追问确认。
2. 系统必须实现四层语义匹配：热词词典→行业词库→向量检索→LLM 兜底，逐层递进、命中即停。
3. 系统必须内置 V1 热词词典种子（10–15 热词映射 + 2–3 锁定公式 + 5–10 行业术语）。
4. 系统必须按管道顺序编排：时间前置→语义匹配→后置标准化→SQL 生成→安全校验→审核阻断→SQL 执行→结果总结。
5. 系统必须对生成的 SQL 做安全校验（黑名单 DML/DDL、白名单 LIMIT≤1000 + 禁止 SELECT *、`sqlparse` 语法）。
6. 系统必须将安全失败原因告知用户，并将失败信息回传 LLM 重生成 SQL（最多 1 次）；仍失败则阻断。
7. 系统必须收集所有 `need_confirm=True` 项（LLM 兜底匹配 + Phase 4 未解值 + 量词），批量一次展示给用户确认。
8. 系统必须用只读连接 + `statement_timeout` 执行 SQL，捕获错误并告知用户（V1 不做自愈）。
9. 系统必须限制单次查询的 LLM 调用次数（`pipeline_llm_max_calls`，默认 5），超限降级。
10. 结果总结 LLM 仅对聚合查询结果做自然语言包装；行级查询直接返回表格、不经过 LLM。
11. 系统必须在不可恢复步骤失败时终止并返回友好错误；可恢复步骤失败时降级继续。

## 业务规则

- **四层递进**：热词(确定性)→行业词(领域)→向量(相似度 top-k)→LLM(兜底，`need_confirm=True`)。每层命中即停。
- **审核阻断**：LLM 兜底匹配 + Phase 4 `need_confirm` 项合并为用户确认；确认后执行，拒绝后返回修正。V1 无管理端审核队列。
- **单步约束**：安全校验拦截 FROM 子句含多个表别名的 SQL（V1 不支持多表 JOIN）；告知用户复杂查询延 Phase 6。
- **安全失败**：黑名单/白名单/语法任一失败 → 阻断 + 告知原因 + LLM 重生成一次 → 仍失败 → 最终阻断。
- **SQL 故障**：超时/执行错误 → 捕获错误、告知用户（含原因和原始 SQL），不做自愈重试。
- **结果总结合规**：仅对聚合查询结果（COUNT/SUM/AVG 等）做 LLM 自然语言包装；行级查询返回表格，不经 LLM——与 Phase 2 L2「不下发原始数据行」治理一致。
- **LLM 调用上限**：`pipeline_llm_max_calls`（默认 5，含语义兜底+SQL 生成+安全重生成+结果总结），超限后跳过结果总结、直接返回表格。
- **管道异常**：不可恢复（目标库不可达、安全校验最终失败）→ 终止 + 友好错误；可恢复（向量检索超时）→ 降级（跳过向量、直接用 LLM 兜底）。

## 边界情况与错误状态

- 空输入 → 拒绝，告知用户输入查询内容。
- SQL 不含 SELECT → 安全校验拦截。
- 目标数据源未激活或不可达 → 终止，告知用户。
- 语义匹配全四层未匹配 → 告知用户无法理解查询。
- 向量检索超时 → 降级，跳过向量直接走 LLM 兜底。
- LLM 调用次数达 `pipeline_llm_max_calls` → 跳过剩余 LLM 步骤、降级（如跳结果总结）。
- 生成的 SQL 涉及多表 FROM → 安全校验拦截为「单步约束」，告知用户。
- Phase 4 标准化器抛错 → 该值 `need_confirm=True`（如同 Phase 4 统一模式），不阻断管道。

## 数据与状态

- **热词词典**（内存字典，V1 非持久化）：`{term: {target_table, target_column, formula(可选), locked(可选)}}`。
- **行业词库**（同上）：`{industry_term: hot_word}`。
- **查询结果**：`{columns, rows, execution_time_ms, sql}` 临时对象，不持久化。
- **管道状态**（运行期）：单次查询的中间产物（匹配结果列表、NormalizedValue 列表、生成的 SQL、安全校验结果、确认状态）。

## 权限与合规

- **查询用户**：发起查询（Phase 9 统一认证前无鉴权）。
- **目标库访问**：只读账户（复用 Phase 2 `query_executor` 的 `SET TRANSACTION READ ONLY` + `statement_timeout`）。
- **LLM 数据治理**：
  - 语义匹配 LLM 兜底：仅结构化信号（字段名+描述，与 Phase 2 L2 一致）。
  - SQL 生成 LLM：输入 schema 上下文（表.列名+类型+语义描述）+ 标准化值 + 用户原句，不含原始数据行。
  - 安全重生成 LLM：输入历史失败原因+原 SQL，不含数据行。
  - **结果总结 LLM**：V1 仅对聚合查询结果（COUNT/SUM/AVG）做自然语言包装；行级查询结果**不经过 LLM**（直接返回表格），与 Phase 2 L2 治理一致。

## 发布与运营

- **迁移**：无（热词词典为代码常量/配置文件，不涉及 schema 变更）。
- **功能开关**：`PIPELINE_ENABLED`（默认 true）。
- **LLM 管控配置**：`pipeline_llm_max_calls`（默认 5）、复用 `learning_job_timeout_minutes` 模式但改为查询级超时。
- **运行时依赖**：Phase 2 LLM caller（复用 `llm/client.py`）、Phase 3 向量检索 + 图谱查询、Phase 4 标准化器 + 映射中心；目标库 `query_executor`。
- **监控/告警**：V1 仅记日志（LLM 调用次数、安全拦截次数、SQL 执行耗时）；自动告警延 Phase 11。
- **回滚**：禁用 `PIPELINE_ENABLED` 即可。

## 实现决策

- **模块边界**：`src/semantic/`（matcher.py + hot_words.py）、`src/sql/`（generator.py + security.py + executor.py）、`src/pipeline/`（single_step.py 编排器）。
- **接口契约**：
  - 入口：`run_single_step_query(nl_text: str, session: AsyncSession, data_source_id) -> QueryResult`
  - 内部：语义匹配模块输入（用户原文 + data_source_id）、输出（匹配结果列表）；SQL 生成输入（匹配结果 + NormalizedValue 列表 + 用户原文）、输出 SQL 字符串。
- **热词 V1 存储**：Python 字典常量（文件 `hot_words.py`），运行时加载到内存，管理员通过编辑代码/配置文件维护（Phase 10 再 CRUD 化）。行业词库同。
- **单步约束机制**：安全校验中增加 `sqlparse` 解析 FROM 子句，若表别名数 >1 则拦截为多步查询。
- **LLM 调用追踪**：每次管道步骤调用 LLM 前检查计数器，达上限则降级。
- **依赖**：Phase 3 `search_fields`（向量检索）+ `shortest_join_path`（但单步不需要 JOIN 路径，延期到 Phase 6）、Phase 4 `parse_time`/`normalize_enum`/`normalize_region`/`normalize_name`/`detect_quantifier`。

## 测试决策

- **测外部行为**：管道输入→输出（正常路径、need_confirm 路径、安全拦截、LLM 降级）。
- **Mock 边界**：LLM caller（所有 LLM 调用可 mock）、向量检索（可 mock Phase 3 `search_fields`）、目标库 `query_executor`（SQL 执行可 mock）。Phase 4 标准化器可用真实 PG（已有测试基础设施）。
- **集成测试**：语义匹配器 + 标准化器 + SQL 生成器的**纯逻辑管道**（mock LLM + mock 目标库）——验证匹配到标准化到 SQL 生成的正确性。
- **端到端验收**：需要真实目标库（任意有数据的 PG/MySQL）+ 真实 LLM + Phase 3/4 全链路。可手工：对含 `orders` 表的目标库输入「昨天的订单总数」，验证返回正确数字。
- **现有模式**：参考 `learning` / `knowledge` / `normalizer` 包行为测试（公共入口、mock 外部）。
- **手工验收**：「查一下昨天的订单总数」→ 端到端输出正确结果。

## 验收标准

- Given NL「查一下昨天的订单总数」，When 单步管道运行，Then 返回正确 COUNT 值（时间前置→语义匹配→标准化→SQL 生成→安全→执行→结果总结）。
- Given 语义匹配命中热词「销售额」，When 运行，Then `matched_by="hot_word"`（第 1 层）。
- Given 向量检索命中 `orders.status`，When 运行，Then `matched_by="vector"`（第 3 层）。
- Given LLM 兜底匹配 `need_confirm=True`，When 运行，Then 与 Phase 4 need_confirm 项**合并一次批量追问**用户确认。
- Given 安全校验命中黑名单，When 运行，Then 用户收到原因说明 + LLM 重生成一次；再失败→最终阻断。
- Given 聚合查询结果，When 结果总结，Then `pipeline_llm_max_calls` 未超限时 LLM 做自然语言包装；超限→直接返回表格。
- Given 行级查询结果，When 结果总结，Then 直接返回表格（不经过 LLM）。
- Given SQL 执行超时，When 运行，Then 捕获错误、告知用户（含原因和原始 SQL），不做自愈重试。
- Given 管道中向量检索超时，When 运行，Then 降级跳过向量、直接走 LLM 兜底（不终止管道）。

## 开放问题

1. **LLM 调用次数默认上限**（owner: 实现者）：`pipeline_llm_max_calls=5` 是否合理（典型路径 2-3 次，安全失败+1-2 次）？不解决：上限过高→成本失控，过低→降级频繁。
2. **热词词典与行业词库 V1 具体清单**（owner: @yanheng）：10–15 热词、5–10 行业术语的精确列表需在实现期从真实业务场景中抽象——PRD 不给完整列表。不解决：实现者需自行补，可能与用户预期差异。
3. **单步约束的「单表」判定规则**（owner: 实现者）：是否允许 FROM 子查询？`sqlparse` 拦截规则有多严？不解决：可能误拦合法单表查询（如子查询做聚合），或漏过多表 JOIN。

## 补充说明

- **设计基线**：`docs/自然语言数据库查询需求设计.md` §八 语义匹配 + §十 安全审核 + §三 3.1 正常流程；`docs/development-plan.md` Phase 5。
- **规格来源**：`team-spec/active/2026-06-19-semantic-matching-pipeline/spec/refine.md`（5 轮）+ `spec/reviews.md`（Status: ready）。
- **Phase 3/4 现实**：Phase 3 知识库已实现（PR #22）；Phase 4 值标准化已实现（PR #29）。Phase 5 调用它们的公共 API。
- **Phase 2 治理先例**：LLM 不下发原始数据行，Phase 5 结果总结同样遵守（发聚合不发行级）。
- **后续工程 issue 预拆**：A 热词词典+行业词库（3.4 收编）、B 语义匹配器（四层递进）、C SQL 生成器、D 安全校验、E SQL 执行器、F 单步管道编排（+ 审核阻断 + LLM 管控）。建议顺序：A → B → C/D/E 并行 → F。
