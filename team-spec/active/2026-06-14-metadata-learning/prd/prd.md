# 元数据学习（Phase 2）— L0/L1/L2 语义描述与外键推断

## 问题陈述

Phase 1 只从目标数据源提取了**结构元数据**（表/字段/索引/显式外键），系统缺少「这个字段在业务上是什么意思」「这两张表怎么关联」的**语义层**。没有这一层：

- Phase 5 语义匹配无法把用户的口语（含行业黑话）映射到具体字段；
- Phase 6 多步查询无法发现表之间的 JOIN 路径——尤其生产业务库（MySQL 常见）普遍**不声明外键**，仅有结构元数据时 JOIN 发现会大面积退化。

需要一个自动学习链路：在元数据提取完成后，为每张表/每个字段产出**带来源标注与置信度的语义描述**，并**推断未声明的外键关系**，供下游语义匹配、SQL 生成、图谱 JOIN 路径发现消费。

本 PRD 是事后规格 + 差距标注：L0–L2 主路径已大半实现并符合设计，本 PRD 描述完整目标行为，并把已识别的缺口与偏差固化为工程 issue（A 外键推断 / B 覆盖率修复 / C L2 治理与并发安全）。

## 目标

- 每张表、每个字段都有**可溯源**的语义描述（`source` + `confidence`），来源优先级：库注释 > 规则推断 > LLM 推断。
- 学习链路在元数据提取完成后自动触发；管理员可手动重跑。
- 推断未声明的外键关系（值重叠度 + 字段名相似度），与显式外键分离存储，供图谱层消费。
- 学习结果可观测：覆盖率口径真实、学习日志记录各层计数与状态。
- L2 LLM 调用受并发、超时、调用数上限三重控制，且 V1 不向外部 LLM 外发任何原始业务数据行。

## 非目标

- **L3 人工补充**（图谱可视化确认界面）—— 延期 Phase 10。
- 向量库 / 图谱构建（Phase 3）。
- 值映射、热词词典（Phase 3）。
- **V1 不向外部 LLM 外发原始采样行**（数据治理约束；Phase 10 治理框架就绪后受控重评估）。
- 重跑时按置信度重新评估/升级已有描述（fill-once，记为已知限制 [D1]）。
- **schema 同步自动触发重学习**（V1 不接；是否接见开放问题 1）。
- 字段名拆词词表的运营维护。
- 监控告警、partial_success/failed 的自动运营处置（Phase 11）。

## 用户与场景

1. 作为**系统（auto 触发）**，我希望在数据源首次元数据提取完成后自动跑 L0→L1→L2，给每列/每表补语义描述，以便下游无需人工即可获得语义层。
2. 作为**管理员（manual 触发）**，我希望在 schema 变更或描述质量不满意时手动重跑学习，以便刷新语义描述与推断外键。
3. 作为**下游系统**（Phase 3 图谱 / Phase 5 语义匹配），我希望读取带 `source` 与 `confidence` 的语义描述与推断外键，以便按可信度决策（高置信度优先、低置信度降级或人工确认）。
4. 作为**管理员**，我希望查看学习日志（各层计数、LLM 调用数、状态、错误），以便判断学习质量与是否需要重跑。

## 当前状态

Phase 2 主路径已实现，符合设计基线：

- **L0 注释提取**：已建。表/列有库注释且未覆盖时写入，`source=schema_comment`、`confidence=1.0`。
- **L1 字段名拆词**：已建（CamelCase / snake_case 拆分 + 中英词表翻译），成功写入 `source=rule_inference`、`confidence=0.7`。
- **L1 数据模式检测**：已建（枚举值、NULL 比例、数值范围），含大表采样；写入独立统计字段，不参与 `source`。
- **L2 LLM 语义推断**：已建骨架（并发信号量、整体超时、429 退避重试、JSON 解析），但存在 3 处需修正的偏差（见下）。
- **编排与来源标记**：已建（L0→L1 拆词→L1 模式检测→L2，来源/置信度矩阵齐全，学习日志记录计数与状态）。

缺口与偏差（本 PRD 固化为 issue A/B/C）：

- **缺口 A — 值重叠度外键推断**：设计 §七 L1 与开发计划 2.2 要求，代码与数据模型均无。决策 0001 已接受纳入 V1。
- **偏差 B — 覆盖率口径失真（bug）**：当前覆盖率把模式检测写入 `null_ratio` 的列（≈全表）也计入「已描述」，并与 L0 双计，使 `success` 判定几乎恒成立、甚至 >100%。
- **偏差 C-1 — L2 下发原始采样行**：当前 L2 把每表 5 行原始业务数据原样发给外部 LLM，仅排除 BLOB 与截断 TEXT，无脱敏/治理。
- **偏差 C-2 — L2 并发共享 AsyncSession**：当前 L2 多表并发共用同一 `AsyncSession`，违反 SQLAlchemy 单任务约束；且 L2 失败被编排层静默吞掉，L2 可能在默认并发下静默 no-op。
- **缺口 C-3 — 无 LLM 调用数上限**：仅有并发与超时，缺单次学习最大调用数，大 schema 有成本失控风险。

## 方案描述

学习链路按四层递进（V1 实现 L0–L2），在元数据提取完成后由系统自动触发，或由管理员手动触发。各层**只填充未覆盖列**（`semantic_description` 为空），一旦写入永不刷新（fill-once [D1]）。

**L0 — Schema 注释提取**：遍历激活数据源的所有表与字段；表/列若有库注释且未覆盖，写入注释，`source=schema_comment`、`confidence=1.0`。

**L1 — 规则推断**，产出两类结果：
- *语义描述*：字段名拆词（CamelCase / snake_case + 中英词表）。成功写入 `source=rule_inference`、`confidence=0.7`；失败留给 L2。
- *结构统计*（独立字段，不参与 `source`）：`detected_enum_values`（去重值 ≤20）、`null_ratio`、`numeric_range={min,max}`。对所有列生效，每表一条聚合查询，大表（>100 万行）走采样。
- *推断外键（缺口 A）*：跨表候选对（数据类型匹配 + 一侧为 PK/unique + 字段名相似度 ≥0.5 门槛）→ 连活库算值重叠率 → 重叠率 ≥0.8（默认，可配）产出一条推断外键，置信度按重叠率映射（≥0.95→0.8；0.8–0.95→0.65），`source=rule_inference`。存新表 `metadata_inferred_fks`，与显式外键 `metadata_foreign_keys` 分离。

**L2 — LLM 语义推断**：仅处理 L0+L1 后仍未覆盖的列，整表一次 prompt。**输入只用结构化信号**（字段名 + 数据类型 + L1 枚举值 + L0 注释 + 拆词结果），**不下发原始业务数据行**（V1 数据治理偏差，Phase 10 受控重评估）。LLM 返回 JSON `{字段名: 语义描述}`，解析失败或字段为 null 则该列留空；命中写入 `source=llm_inference`、`confidence=0.5`。受并发（默认 5）、整体超时（默认 60 分钟）、单次学习最大调用数（默认 200，0=不限）三重控制；429 指数退避重试 3 次，非限流错误不重试。**每个并发任务使用独立的 AsyncSession**（修正偏差 C-2）。

**编排**：L0 → L1 拆词 → L1 模式检测 → L1 外键推断 → L2。L1 模式检测、L1 外键推断、L2 的失败被抑制，不阻断整体流水线。覆盖率 = 该数据源下 `semantic_description` 非空列数 / 总列数：≥0.8 → `success`；>0 → `partial_success`；=0 → `failed`。

## 范围

### 范围内

- L0 注释提取（已建，保持）。
- L1 拆词 + 模式检测（已建，保持）。
- **L1 值重叠度外键推断（缺口 A）**：新表 + 候选生成 + 重叠查询 + 判定与置信度映射 + 编排接入。
- L2 LLM 语义推断：**偏差 C-1/C-2/C-3 修正**（不下发原始行、每表独立 session、调用数上限）。
- 编排：顺序串联、来源/置信度矩阵、**覆盖率口径修复（偏差 B）**、学习日志。
- fill-once 覆盖语义（接受为 V1 [D1]）。

### 范围外

- L3 人工补充界面（Phase 10）。
- 向量库 / 图谱构建（Phase 3）。
- V1 向外部 LLM 外发原始采样行（Phase 10 治理框架就绪后重评估）。
- schema 同步自动触发重学习（V1 不接，开放问题 1）。
- 监控告警与 partial/failed 自动运营处置（Phase 11）。
- 按置信度重评/升级已有描述（[D1] 已知限制）。

## 功能需求

1. 系统必须在激活数据源首次元数据提取完成后自动触发一次完整学习（`trigger_type=auto`）。
2. 管理员必须能手动触发完整学习（`trigger_type=manual`），且同一数据源学习进行中再次触发应被拒绝（互斥）。
3. L0 必须把库注释写入未覆盖的表/列，标记 `schema_comment` / `1.0`。
4. L1 必须对未覆盖列做字段名拆词，成功标记 `rule_inference` / `0.7`。
5. L1 必须对所有列做模式检测，写入枚举值/NULL 比例/数值范围（独立统计字段，不影响 `source`）。
6. **L1 必须推断值重叠度外键**：对满足候选条件的跨表列对计算重叠率，≥阈值产出推断外键行（缺口 A）。
7. L2 必须对 L0+L1 后仍未覆盖的列做整表 LLM 推断，命中标记 `llm_inference` / `0.5`。
8. **L2 必须只发送结构化信号，不得发送原始业务数据行**（偏差 C-1）。
9. **L2 并发必须保证每个任务使用独立 AsyncSession**（偏差 C-2）。
10. **L2 必须受单次学习最大调用数上限约束**，达上限提前停并记日志（缺口 C-3）。
11. 覆盖率必须按 `semantic_description` 非空列占比计算（偏差 B）。
12. 学习日志必须记录 l0/l1/l2 计数、l2_llm_calls、状态、起止时间、错误信息。

## 业务规则

- **来源优先级与置信度矩阵**：库注释 `schema_comment`/1.0 > 拆词 `rule_inference`/0.7 > LLM `llm_inference`/0.5；推断外键 `rule_inference`，置信度按重叠率映射（≥0.95→0.8，0.8–0.95→0.65）。
- **fill-once [D1]**：各层只填 `semantic_description is None` 的列；一旦写入永不刷新。改库注释或想升级已有描述不会自动刷新——已知限制。
- **推断外键判定 [缺口 A]**：候选门槛 = 数据类型匹配 + 一侧为 PK/unique + 字段名相似度 ≥0.5；判定门槛 = 值重叠率 ≥0.8（默认，可配）。
- **推断外键重跑语义**：每次学习对推断外键**重算替换**（先清除该数据源既有推断外键，再按本轮结果写入），不适用 fill-once——因为推断外键是纯 SQL 聚合的派生事实，新鲜度优先于稳定性。
- **覆盖率与状态**：非空列/总列数 ≥0.8 → `success`；>0 → `partial_success`；=0 → `failed`。总列数=0 → `failed`（无可描述列）。**V1 因不下发原始行，含大量无注释列的 schema 可能普遍 `partial_success`，属预期，非告警**（运营处置延 Phase 11）。
- **失败抑制**：L1 模式检测、L1 外键推断、L2 任一失败不阻断整体流水线，状态按已覆盖列判定。
- **触发约束**：仅「首次提取完成」与「手动触发」会跑学习；**schema 同步（diff）不触发学习**，同步新增的列保持未描述直到手动重跑或重新激活（开放问题 1）。

## 边界情况与错误状态

- 有库注释的列 → `semantic_description`=注释，`schema_comment`/1.0。
- 无注释的 `created_at` → L1 拆词得到中文描述，`rule_inference`/0.7。
- 枚举列（如 3 个去重值 / 10000 行）→ `detected_enum_values` 填入这 3 个值。
- 数值列 → `numeric_range={min,max}`；含 NULL 列 → `null_ratio` 正确。
- L0+L1 都搞不定的列（如 `usr_typ_cd`）→ L2 用结构化信号推断，`llm_inference`；**不下发原始行**。
- 1000 去重值 / 1000 行的列 → 比例 1.0，**不**判为枚举。
- 25 去重值 / 10000 行 → 比例 <0.05 但 >20，**不**判为枚举（违反 ≤20）。
- 空表（total_rows=0）→ 不判枚举、不写 `null_ratio`。
- 大表（>100 万行）模式检测走采样，不 OOM、不超时。
- L2 并发跑多表（默认 5）不触发 AsyncSession 并发错误，每表独立 session。
- L2 整表调用返回非法 JSON → 该表列保持未覆盖，不抛错、不阻断。
- LLM 限流耗尽重试 → 该表返回 None，流水线继续。
- LLM 调用数达上限 → 提前停 L2、记日志，流水线仍按已覆盖算 success/partial。
- 外键：`orders.customer_id` 与 `customers.id`（类型匹配、`customers.id` 为 PK、名称相似度 ≥0.5、重叠率 ≥0.8）→ 产出一条推断外键，置信度按重叠率映射；重叠率 <0.8 或名称相似度 <0.5 → 不产出。

## 数据与状态

- **MetadataColumn / MetadataTable**：已有。新增/沿用语义字段：`semantic_description`、`description_source`（`schema_comment`/`rule_inference`/`llm_inference`）、`description_confidence`；结构统计字段：`detected_enum_values`、`null_ratio`、`numeric_range`。
- **metadata_inferred_fks（新表，缺口 A）**：推断外键，按数据源隔离。核心字段：`data_source_id`、`source_table`、`source_column`、`target_table`、`target_column`、`overlap_rate`、`name_similarity`、`confidence`、`source`（=`rule_inference`）。与显式外键 `metadata_foreign_keys` 分离，镜像图谱层 `REFERENCES`（显式）vs `INFERRED_REF`（推断）两种边。完整 DDL 由 issue A 通过 Alembic 迁移最终确定。
- **MetadataLearningLog**：学习日志。`trigger_type`（auto/manual）、`status`（running/success/partial_success/failed/aborted）、`tables_processed`、`columns_described`、`l0_count`、`l1_count`、`l2_count`、`l2_llm_calls`、`started_at`、`finished_at`、`error_message`。
- **生命周期**：学习为幂等批量任务（描述 fill-once；推断外键重算替换）。学习进行中对该数据源的学习触发被互斥拒绝。

## 权限与合规

- **触发权限**：auto 触发由系统在提取完成后发起；manual 触发限管理员（API 鉴权 Phase 9 统一处理，V1 沿用现有管理端约定）。
- **数据治理（V1 约束）**：**学习链路不向外部 LLM（DashScope）外发任何原始业务数据行。** L2 仅用结构化信号推断。依据：V1 无数据治理框架（无管理端 UI、无审计、无授权流），denylist/脱敏都是「尽力而为」——漏判即泄漏；L1 已提供强信号（枚举值/空值率/数值范围/拆词）+ L0 注释，原始行边际价值低。记为 V1 与设计 §七「采样数据」输入的偏差；Phase 10 治理框架（管理端 + 审计 + 可配采样策略/敏感列）就绪后受控重评估。
- **可见性**：语义描述、推断外键、学习日志按数据源隔离；查询用户经下游语义匹配间接消费，不直接访问学习原始数据。

## 发布与运营

- **迁移**：issue A 新增 `metadata_inferred_fks` 表的 Alembic 迁移（高回退成本，已在决策 0001 记录）；issue B/C 不涉及 schema 变更。
- **配置项**：`learning_l2_max_concurrency`（默认 5）、`learning_job_timeout_minutes`（默认 60）、新增 `learning_l2_max_calls`（默认 200，0=不限）、新增 FK 推断重叠率阈值（默认 0.8，可配）。
- **功能开关**：无；学习为提取后的自动行为，行为变更随 issue 上线。
- **issue 落地顺序（重要）**：**Issue C（L2 真正可用）应先于或同批于 Issue B（覆盖率口径修复）落地**。否则单独修 B 会把 L2 在默认并发下静默失效的事实暴露为大面积 `partial_success`/`failed`，运营误判为回归。
- **监控/告警**：V1 仅记学习日志 + 管理端可查 learning-logs；自动监控告警与 partial/failed 运营处置延 Phase 11。
- **回滚**：issue A 的迁移需可回滚（drop 新表）；issue B/C 为代码变更，回滚即恢复旧行为。

## 实现决策

- **模块边界（ownership）**：学习链路集中在 `learning` 包（编排 + L0/L1/L2 + 拆词 + 模式检测 + 外键推断）；数据模型与迁移在 `metadata` 包；配置在 `config.settings`；触发点在数据源激活/手动触发的 API。FK 推断复用既有 `query_executor` 抽象与数据源只读连接，不引入图谱层依赖。
- **接口契约**：L2 入参改为接收 **session factory**（而非单个 session），每个并发任务从 factory 取独立 `AsyncSession`，以满足 AsyncSession 单任务安全不变式。`query_executor` 作为 FK 推断与模式检测共享的「对目标库执行只读 SQL」抽象，含大表采样决策。
- **已确认 schema 决策**：推断外键用**新表** `metadata_inferred_fks`（不扩 `MetadataForeignKey`），与显式外键分离，对应图谱层两种边语义（决策 0001）。
- **fill-once vs 重算**：`semantic_description` fill-once（[D1]）；推断外键每次重算替换。

## 测试决策

- **测外部行为，不测实现细节**：通过 `run_learning` 及各层公共入口验证可观察行为（写入的 `semantic_description`/`source`/`confidence`、结构统计字段、推断外键行、学习日志计数与状态）。
- **Mock 边界**：仅 mock 外部系统——LLM caller（`LLMCaller` 协议）、对目标库的 `query_executor`、时间。不 mock 应用数据库会话（走真实 async session）。
- **必测流程**：
  - 来源/置信度矩阵（L0/L1拆词/L2 三来源各自落库）。
  - 模式检测边界（枚举判定的 3 去重/1000 去重/25 去重三档、空表、数值范围、null_ratio）。
  - 大表采样路径（估计行数超阈值走采样，不超走全量）。
  - **覆盖率口径（偏差 B）**：模式检测写 `null_ratio` 的列不计入「已描述」；`success` 判定按 `semantic_description` 非空占比。
  - **L2 数据治理（偏差 C-1）**：断言 L2 prompt/调用载荷中不含原始业务数据行，仅含结构化信号。
  - **L2 并发安全（偏差 C-2）**：并发 >1（默认 5）跑 L2，每表独立 session，不触发 AsyncSession 并发错误；该测试需走真实 async session，不得用共享 mock session 掩盖。
  - **L2 成本上限（缺口 C-3）**：调用数达 `learning_l2_max_calls` 提前停、记日志、状态按已覆盖判定。
  - **外键推断（缺口 A）**：`orders.customer_id`↔`customers.id` 命中产出推断外键行（置信度按重叠率映射）；重叠率/名称相似度不达门槛不产出。
- **现有测试模式**：参考 `learning` 包已有行为测试（走公共入口、mock `query_executor`/`llm_caller`）。
- **手工验收**：对一个含无注释列与未声明外键的真实 schema 跑一次学习，检查覆盖率状态、推断外键表、学习日志计数符合预期。

## 验收标准

- Given 一列有库注释且未覆盖，When 学习运行，Then `semantic_description`=注释、`source=schema_comment`、`confidence=1.0`。
- Given 无注释的 `created_at` 列，When 学习运行，Then L1 拆词写入中文描述、`source=rule_inference`、`confidence=0.7`。
- Given 一列有 3 个去重值/10000 行，When 学习运行，Then `detected_enum_values` 含这 3 个值。
- Given 一数值列，When 学习运行，Then `numeric_range={min,max}`；含 NULL 列 `null_ratio` 正确。
- Given `usr_typ_cd` 这类 L0+L1 都搞不定的列，When 学习运行，Then L2 用结构化信号推断、`source=llm_inference`，且**未向 LLM 发送任何原始业务数据行**。
- Given 覆盖率（按 `semantic_description` 非空）≥80%，When 学习运行，Then `status=success`；>0 且 <80% → `partial_success`；=0 → `failed`。
- Given 大表（>100 万行），When 模式检测运行，Then 走采样、不 OOM、不超时。
- Given 默认并发 5、多张含未覆盖列的表，When L2 运行，Then 每表使用独立 AsyncSession、不触发并发错误、日志记录真实 l2_count。
- Given `orders.customer_id` 与 `customers.id`（类型匹配、`customers.id` 为 PK、名称相似度 ≥0.5、重叠率 ≥0.8），When 外键推断运行，Then 产出一条 `metadata_inferred_fks` 行、`confidence` 按重叠率映射、`source=rule_inference`。
- Given 一对列重叠率 <0.8 或名称相似度 <0.5，When 外键推断运行，Then 不产出推断外键行。
- Given 手动重跑学习，When 学习运行，Then 推断外键被重算替换（既有推断外键先清除再写入），而 `semantic_description` 仍遵循 fill-once。
- Given LLM 调用数已达 `learning_l2_max_calls`，When L2 运行，Then 提前停 L2、记日志、状态按已覆盖列判定。
- Given L2 整表返回非法 JSON，When 学习运行，Then 该表列保持未覆盖、不抛错、不阻断流水线。

## 开放问题

1. **sync→learning 是否对新增列接上自动重跑？**（owner: @yanheng；不解决：同步新增列保持未描述直到手动重跑，与 fill-once 声明耦合，可能影响 Phase 5 联调体验。V1 建议不接、文档明确，Phase 7/11 再评估。）
2. **`learning_l2_max_calls` 默认值（建议 200）是否合适？**（owner: @yanheng；需结合典型 schema 规模定。不解决：默认过小会提前停 L2、过大有成本失控风险。）
3. **采样何时受控重新开放？**（owner: @yanheng；依赖 Phase 10 治理框架：管理端 + 审计 + 可配敏感列/采样策略就绪后再评估。）
4. **partial_success/failed 的最小运营处置**（V1 仅日志 + 管理端可查，自动告警延 Phase 11）是否可接受？（owner: @yanheng。）

## 补充说明

- **设计基线**：`docs/自然语言数据库查询需求设计.md` §七 元数据学习系统；`docs/development-plan.md` Phase 2（2.1–2.4）。
- **规格来源**：`team-spec/active/2026-06-14-metadata-learning/spec/refine.md`（第二轮 review-driven 修订）+ `spec/decisions/0001-fk-inference-in-learning.md`（accepted）。
- **评审结论**：`spec/reviews.md`，Status: `ready`（首轮 4 个 P1 已全部闭合并经代码核验；残余 P2/P3 已吸收进本 PRD 或列入开放问题）。
- **全局上下文**：`team-spec/CONTEXT.md`（术语表、角色、通用规则）。
- **后续工程 issue 预拆（供 `team-prd-to-issues`）**：A 值重叠度外键推断（含迁移 + [D2] docstring 顺手修）、B 覆盖率口径修复、C L2 治理 + 并发安全 + 调用数上限。落地顺序：C 先于或同批于 B。
- **已知偏差记录**：[D1] fill-once 不刷新；[D2] `run_learning` docstring 过时（Issue A 顺手修）；[V1] L2 不下发原始采样行（数据治理偏差）。
