# 查询值标准化（Phase 4）— 口语值→结构化值 + 值映射中心

## 问题陈述

用户的自然语言查询携带口语化的**值表述**——「上个月」「大客户」「华东」「已完成」「华为」——这些 SQL 不能直接消费。Phase 5 语义匹配先识别「用户说的是哪个表的哪一列」，但识别之后还需要把「用户说的值」转换成 SQL 可用的形式：时间解析为日期范围、枚举别名映射为真实值、区域展开为城市列表、名称简称匹配为全称、模糊量词引发追问。此外，这些映射数据（枚举别名、区域字典、名称简称）需要**持久化存储与 CRUD API**——Phase 3 延期的「值映射中心」由本 Phase 收编。

## 目标

- 用户输入「上个月上海大额的已支付订单」，系统自动标准化：「上个月」→ 日期范围、「上海」→ `city IN ('上海')`、「大额」→ 追问确认、「已支付」→ 枚举值 `status='paid'`。
- 管理员可通过 API 管理激活数据源的枚举别名映射、区域字典、名称简称，无需改代码。
- 各标准化策略用尽后统一返回 `need_confirm=True`，Phase 6 批量一次性向用户追问（不逐字段打断）。
- 枚举 LLM 兜底调用与 Phase 2 L2 一致：**仅结构化信号，不下发原始业务数据行**。

## 非目标

- **3.4 热词词典**（含锁定业务指标公式 / 固定日期型周期配置）—— 继续独立，归 Phase 3.b 或 Phase 5 前置。
- 语义匹配 / SQL 生成 / 多步编排（Phase 5/6）。
- 管理端 UI（Phase 10）；本规格只做后端标准化器 + 配置 CRUD API。
- 模糊量词的自定义量化规则（大额 > 10000 这类规则不由 Phase 4 定义，追问让用户明确）。
- 动态相对周期（财年、农历）——明确排除，引导用户用绝对日期。

## 用户与场景

1. 作为**查询用户**，我说「上个月上海大额的已支付订单」，系统自动把「上个月」→ 日期范围、「上海」→ `city IN ('上海')`、「已支付」→ `status='paid'`，「大额」→ 追问确认金额阈值。
2. 作为**查询用户**，我说「华为的合同」，系统通过名称简称匹配把「华为」标准化为数据库里的 `Huawei Technologies`。
3. 作为**查询用户**，当模糊量词（「大额」「大量」）被检测到时，系统不自动量化而是追问，避免业务定义错误。
4. 作为**管理员**，我希望通过 API 管理枚举别名（「已完成」→ `completed`）、区域字典（自定义销售大区）、名称简称，无需改代码。
5. 作为**Phase 5 语义匹配 Agent**，我希望按 `(field_context, raw_value)` 调标准化引擎，获得 `NormalizedValue` 列表供 Phase 6 SQL 生成消费。

## 当前状态

- **Phase 1**：`detected_enum_values`（L1 模式检测）可作为枚举别名种子。
- **Phase 2**：LLM 治理先例（仅结构化信号、不下发原始行）可直接沿用。
- **Phase 3**：知识库已建（向量+图谱），可用于名称匹配 strategy 7（向量语义匹配）。
- **缺口**：`src/normalizer/` 为空，无任何标准化器代码；值映射存储不存在（3.5 收编）；Phase 5/6 尚未实现（Phase 4 需要一个稳定的接口契约，但端到端验证依赖后续 Phase）。

## 方案描述

**主路径**：Phase 5 语义匹配识别到字段后，按 `(field_context = {table, column, data_source_id}, raw_value = 用户原文)` 调用 Phase 4 标准化引擎。引擎根据 field_context 的数据类型和映射数据选择对应标准化器（时间/枚举/区域/名称/数值），执行策略链。标准化成功 → 返回 `NormalizedValue{db_representation, confidence, matched_by}`；全部策略用尽 → 返回 `NormalizedValue{need_confirm=True, db_representation=None, confidence=0}`。Phase 6 收集所有 `need_confirm` 值，**批量一次性**向用户展示追问。

**时间标准化可在语义匹配之前独立运行**（不依赖字段上下文），提前提取查询中的时间表述。

**层级示意图**：
```
用户输入 → Phase 5 语义匹配(识别字段) → Phase 4 值标准化(策略链+映射查询) → Phase 6 SQL 生成
                ↑ 时间可前置提取 ↑
```

## 范围

### 范围内

- **4.1 统一数据结构**：`NormalizedValue`（original/normalized/value_type/db_representation/confidence/matched_by/need_confirm/alternatives）。
- **4.2 时间表述标准化**：相对时间（今天/昨天/本周/上周/本月/上月/本季度/今年）+ 绝对时间（2026年5月/2026-05-01）+ 固定日期型自定义周期（双十一/618）。
- **4.3 枚举值映射**：5 策略递进（字典表实时查询→精确匹配 display→别名匹配 aliases→编辑距离≥0.7 模糊→LLM 兜底 confidence>0.85，仅结构化信号不发原始行）。
- **4.4 区域/地名处理**：粒度自适应（区域/城市/区级）+ 层级包含展开为 SQL IN。
- **4.5 名称简称匹配**：7 策略递进（精确→简称→别名→拼音→关键字→编辑距离≥0.7→向量语义）；全失败回退到目标库 `SELECT DISTINCT col FROM table WHERE col LIKE '%xxx%' LIMIT 10`（复用 query_executor）；仍失败→need_confirm。
- **4.6 数值范围处理**：模糊量词检测（高价值/大额/小额/适中/大量/少量）→ 始终 need_confirm，不自动量化。
- **3.5 值映射中心（收编）**：枚举别名表 + 区域字典表 + 名称简称表的仓库存储 + CRUD API（按 data_source_id 隔离）。

### 范围外

- 3.4 热词词典（→ Phase 3.b / Phase 5 前置）。
- 语义匹配 / SQL 生成 / 多步编排（Phase 5/6）。
- 管理端 UI（Phase 10）。
- 动态相对周期、自定义量化规则。
- Phase 4 不负责「什么时候调用标准化」的编排——那是 Phase 5 的职责。Phase 4 只提供标准化能力本身。

## 功能需求

1. 系统必须提供 `NormalizedValue` 数据结构，包含 original / normalized / value_type / db_representation / confidence / matched_by / need_confirm / alternatives 字段。
2. 系统必须提供时间标准化器：解析相对时间、绝对时间、固定日期周期，输出日期范围 SQL 片段。
3. 系统必须提供枚举标准化器：5 策略递进，LLM 兜底仅用结构化信号（字段名 + 枚举值列表 + 用户输入），不下发原始业务行。
4. 系统必须提供区域标准化器：粒度自适应，支持预设中国行政区划 + 管理员自定义区域。
5. 系统必须提供名称标准化器：7 策略递进，全失败回退目标库 LIKE（复用 query_executor + 只读 + 限流 LIMIT 10）。
6. 系统必须提供数值标准化器：检测模糊量词 → need_confirm。
7. 所有标准化器策略用尽时统一返回 `NormalizedValue(need_confirm=True, db_representation=None, confidence=0)`。
8. 管理员必须能通过 API 对激活数据源做枚举别名、区域字典、名称简称的增删改查（含批量导入）。
9. 枚举别名在首次学习完成后自动从 `detected_enum_values` 采集种子记录（value+display=原始值+空别名）；管理员可补充别名。
10. 激活新数据源时，系统自动将该源的区域字典导入预设的中国行政区划 CSV 种子数据。
11. 删除数据源时，该源的映射数据同步清理（`CASCADE` 或应用层手动清理）。

## 业务规则

- **标准化顺序**：时间可前置提取；枚举/区域/名称在字段识别后按 field_context 选择对应的标准化器；数值量词检查最后。
- **策略链递进**：枚举（字典表→精确→别名→编辑距离→LLM）/ 名称（精确→简称→别名→拼音→关键字→编辑距离→向量），每一步命中即停止，全失败触发降级（枚举→need_confirm，名称→LIKE 回退后再判断，区域→need_confirm）。
- **LLM 治理**：枚举 LLM 兜底仅发结构化信号——字段名 + 已知枚举值列表 + 用户口语文本，不下发原始业务数据行。与 Phase 2 L2 治理一致。
- **名称 LIKE 回退**：目标库只读、`LIMIT 10`、复用 `query_executor` 抽象；超时/限流在实现期定义（复用 Phase 2 模式检测的连接安全策略）。
- **追问统一**：need_confirm=True 不逐字段打断；Phase 6 批量展示所有待确认项一次。
- **映射存储隔离**：枚举别名/区域字典/名称简称全按 `data_source_id` 命名空间隔离；区域提供全局种子可导入到各源。
- **固定日期周期**：代码常量预设值（双十一 11-01∼11-11 / 618 06-01∼06-18），管理员可通过 CRUD 增删。

## 边界情况与错误状态

- 区域字典中不存在的城市 → need_confirm。
- 枚举 LLM 兜底失败 → need_confirm。
- 名称 LIKE 回退返回 0 行 → need_confirm，alternatives 为空。
- 名称 LIKE 回退时目标库不可达 → 静默跳过 LIKE，need_confirm。
- 数值模糊量词检测到但无阈值定义 → need_confirm。
- 字段上下文为空或未知类型 → 不做标准化，返回 need_confirm。
- 映射存储中同一列的不同枚举值均未匹配 → 全部 need_confirm，Phase 6 批量追问。
- 编辑距离匹配多个候选 → 按距离排序，取最近且≥阈值的第一个；多个等距且未明确区分 → need_confirm。

## 数据与状态

- **NormalizedValue**（运行期对象，非持久化）：`{original, normalized, value_type, db_representation, confidence, matched_by, need_confirm, alternatives}`。
- **枚举别名表** `value_enum_mappings`：`id, data_source_id(FK→data_sources CASCADE), table, column, value(DB 实际值), display(展示名), aliases(JSONB 别名数组), created_at, updated_at`。唯一约束：`(data_source_id, table, column, value)`。
- **区域字典表** `value_region_dict`：`id, data_source_id(FK), parent_code(上级编码，NULL=顶级), level(province/city/district/custom), code(区域编码), name, aliases(JSONB), created_at`。
- **名称简称表** `value_name_mappings`：`id, data_source_id(FK), short_name, full_name, target_table(可选), aliases(JSONB), created_at`。唯一约束：`(data_source_id, short_name)`。
- **固定日期周期**（代码常量 + 可能的配置表 `value_fixed_periods` 扩展）：含 `name, start_mmdd, end_mmdd`。
- **生命周期**：映射数据随数据源激活初始化（枚举自动采集、区域导入种子）；随删除清理。管理员 CRUD 实时生效。标准化器运行时只读。

## 权限与合规

- **查询用户**：只读消费标准化能力（无直接 API 入口，经 Phase 5 间接调用）。
- **管理员**：通过 CRUD API 管理映射数据（Phase 9 统一认证前无额外鉴权）。
- **数据治理**：枚举 LLM 兜底下发外部 LLM 的内容为结构化信号（字段名 + 枚举值列表 + 用户输入），**不含原始业务数据行**；与 Phase 2 L2 治理先例一致。
- **名称 LIKE 回退**：对目标业务库发起只读 LIKE 查询，复用 Phase 2 `query_executor` 的 `SET TRANSACTION READ ONLY` + `statement_timeout` 安全约束。

## 发布与运营

- **迁移**：新增 3 张映射表（`value_enum_mappings`, `value_region_dict`, `value_name_mappings`）的 Alembic 迁移。目标库 `information_schema` 访问不变。
- **功能开关**：无独立开关。标准化器作为 `normalizer` 包的库函数提供，Phase 5 接入后才生效。
- **种子数据**：枚举别名在首次学习后自动采集（Phase 2 run_learning 完成后异步补）；区域 CSV 在数据源激活时导入。
- **运行时依赖**：复用 Phase 2 `query_executor` 抽象（名称 LIKE 回退）+ Phase 3 向量检索（名称 strategy 7）+ 现有 LLM/DashScope 配置（枚举 LLM 兜底）。
- **监控/告警**：V1 仅记日志。LLM 调用日志、LIKE 回退命中次数延 Phase 11。
- **回滚**：删除新迁移的 3 张映射表 + 移除标准化器调用（降级为原始值直传）。

## 实现决策

- **模块边界**：`src/normalizer/` 包（types.py + time_parser.py + enum_matcher.py + region_parser.py + name_matcher.py + quantifier.py）。值映射中心 CRUD 放在 `src/api/`（复用 datasources 路由模式）或独立 `src/normalizer/api.py`。
- **接口契约**：
  - Phase 5 → Phase 4：`normalize(field_context: {table, column, data_source_id}, raw_value: str) -> NormalizedValue`
  - Phase 4 → Phase 6：传入 `NormalizedValue` 列表，用 `db_representation` 构造 SQL；`need_confirm` 项批量追问。
  - 时间标准化提供独立入口 `parse_time(raw_value) -> NormalizedValue` 供 Phase 5 前置调用。
- **映射表 schema**：见「数据与状态」章节（3 张表 + 唯一约束）。
- **区域 CSV 格式**：4 列——`code,parent_code,level,name`（parent_code 空表示顶级；level 取值 province/city/district）。格式为无 header 的 UTF-8 CSV。
- **固定日期周期预设**：V1 初始值 `{"双十一": "11-01/11-11", "618": "06-01/06-18"}`。管理员可增删。
- **名称 LIKE 回退参数**：`LIMIT 10`；超时沿用 `statement_timeout`（与 Phase 2 模式检测一致）；复用 `query_executor` 抽象。
- **依赖**：Phase 1 `detected_enum_values`（种子）、Phase 2 LLM 治理先例 + `query_executor`、Phase 3 向量检索（名称 strategy 7）。

## 测试决策

- **测外部行为**：每个标准化器的策略链（输入→预期 `NormalizedValue`）。纯函数测试：时间解析、枚举匹配/编辑距离、区域粒度、名称字符串匹配、数值量词检测——这些不依赖外部服务。
- **Mock 边界**：LLM 调用（枚举 strategy 5）、embedding 服务（名称 strategy 7 向量）、目标库 `query_executor`（名称 LIKE 回退）。应用库会话走真实 PG。
- **集成测试**：枚举/区域/名称的 CRUD API + 标准化器读写映射表（真实 PG）；名称 LIKE 回退 mock `query_executor`。
- **端到端验证 gate**：Phase 4 的端到端验证（「用户输入→SQL」闭环）依赖未实现的 Phase 5/6。单测 + mock 覆盖所有策略链；端到端 gate 标为 Phase 5 联调时验证。
- **现有模式**：参考 `learning` 包行为测试（公共入口、mock 外部依赖）。
- **手工验收**：对含已知枚举别名与区域的测试数据源，跑每个标准化器的策略链，验证返回的 `NormalizedValue` 各字段正确。

## 验收标准

- Given `field_context={orders.status}` + `raw_value="已完成"` 且枚举别名为 `"已完成"→"completed"`，When 枚举标准化，Then `NormalizedValue{db_representation="completed", matched_by="alias", confidence>0, need_confirm=False}`。
- Given `raw_value="上个月"`，When 时间标准化，Then `NormalizedValue{value_type="time", db_representation=上月日期范围 SQL 片段}`。
- Given `raw_value="上海"` 且区域字典有 `上海`，When 区域标准化，Then `NormalizedValue{db_representation=city IN ('上海')}`。
- Given `raw_value="华为"` 且名称简称表有 `"华为"→"Huawei Technologies"`，When 名称标准化，Then `NormalizedValue{db_representation="Huawei Technologies", matched_by="short_name"}`。
- Given 枚举/区域/名称全策略失败，When 标准化，Then `NormalizedValue{need_confirm=True, db_representation=None, confidence=0}`。
- Given `raw_value="大额"`，When 数值标准化，Then `NormalizedValue{need_confirm=True, value_type="quantifier"}`。
- Given 枚举 LLM 兜底被触发，When 调用，Then 发送的 prompt 仅含字段名+已知枚举值列表+用户输入、**不含原始业务数据行**。
- Given 名称全策略失败，When 名称标准化，Then 对目标库发起 `SELECT DISTINCT col FROM table WHERE col LIKE '%xxx%' LIMIT 10`，结果作为 alternatives。
- Given 管理员 POST 一条枚举别名映射，When 查询，Then 标准化器能命中该别名。
- Given 管理员 DELETE 一条枚举别名映射，When 标准化器运行，Then 该别名不再命中。
- Given 一个数据源被删除，When 删除完成，Then 该源的枚举别名/区域字典/名称简称记录全部清理。

## 开放问题

1. **Phase 5/6 契约稳定性**（owner: @yanheng）：Phase 4 针对的是一个 `normalize(field_context, raw_value) → NormalizedValue` 的假设契约——Phase 5/6 尚未实现。若 Phase 5 落地时契约调整，Phase 4 可能需要返工。不解决：Phase 4 实现与验证阶段只能用 mock 的 Phase 5 上下文；端到端闭环 gate 到 Phase 5。
2. **名称 LIKE 回退的目标库参数**（owner: 实现者）：超时 `statement_timeout`、限流机制与现有 `query_executor` 模式是否完全兼容。不解决：目标库 LIKE 可能超时/慢查阻塞标准化链路。
3. **区域种子 CSV 的具体来源**（owner: @yanheng）：中国行政区划数据从哪获取（开源数据集/内置代码/管理界面上传）。不解决：激活新源时区域字典为空、区域标准化不可用。
4. **固定日期周期与 Phase 3.4 热词词典的边界**（owner: @yanheng）：固定日期周期原属 Phase 3.4（开发计划中热词词典包含），本规格将它们挪入 Phase 4 时间标准化。需确认 3.4 不再持有日期周期。

## 补充说明

- **设计基线**：`docs/自然语言数据库查询需求设计.md` §四 查询值标准化系统；`docs/development-plan.md` Phase 4（4.1–4.6）。
- **规格来源**：`team-spec/active/2026-06-19-query-value-normalization/spec/refine.md`（5 轮细化）+ `spec/reviews.md`（Status: ready，P1 LLM 治理 + 5 项 P2）。
- **Phase 3 延期决策**：Phase 3 规格明确延期 3.4 热词词典、3.5 值映射中心。本 PRD 收编 3.5，3.4 继续独立。
- **Phase 2 先例**：LLM 治理（不下发原始行）、`query_executor` 抽象（FK 推断/模式检测的只读连接模式）可直接复用。
- **后续工程 issue 预拆（供 `team-prd-to-issues`）**：A NormalizedValue + 时间标准化器、B 枚举标准化器 + LLM 兜底、C 区域标准化器、D 名称标准化器 + LIKE 回退、E 数值标准化器、F 值映射中心 CRUD + 迁移 + 种子数据。建议顺序：A/F 可并行 → B/C/D/E 可并行（各标准化器独立）。
