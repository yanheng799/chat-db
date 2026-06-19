# 规格评审 — 查询值标准化（Phase 4）

- **slug**：`2026-06-19-query-value-normalization`
- **评审日期**：2026-06-19
- **评审对象**：`spec/refine.md`（5 轮细化完成版）
- **评审依据**：设计文档 §四 查询值标准化系统、开发计划 Phase 4（4.1–4.6）、Phase 3 延期决策（3.5 收编）、Phase 2 L2 治理先例（LLM 不下发原始行）、`src/normalizer/`（空）、`src/config/settings.py`（已有 embedding/llm 配置）
- **Status**：`ready`（无 P0；P1 为 LLM 兜底治理——有 Phase 2 先例、已接受；其余为 P2/P3，可在 PRD/issue 阶段跟踪）

## 结论

规格可进入 PRD 固化：5 轮细化覆盖范围收编（3.5+4.1–4.6）、流水线位置、数据隔离、失败/追问策略、种子数据策略，验收口径可观察、可测试。无 P0，无阻塞 PRD 固化的 P1。最大风险来自**「技术依赖 + 测试验收」**维度——Phase 4 依赖 Phase 5/6 的接口契约（Phase 4 等待 Phase 5 提供字段上下文、Phase 6 消费 NormalizedValue），但 Phase 5/6 尚未实现，Phase 4 在这之前无法端到端验证。

## 阻塞项

无（不阻塞 PRD 固化）。P1（LLM 兜底治理）已在 Phase 2 L2 决策接受、本规格沿用，不在此处升级为 blocker。

## 风险清单

| 等级 | 风险 | 触发条件 | 影响 | 证据/缺口 | 建议动作 | Owner | 截止点 |
|---|---|---|---|---|---|---|---|
| P1 | 枚举 LLM 兜底外发数据治理 | 标准化器调用 LLM 兜底 | 外部 LLM 可能收到业务相关的枚举值/用户口语；无审计/越权 | 与 Phase 2 L2 同类风险（已决策接受：仅结构化信号、不下发原始行）；本规格枚举 LLM 调用同样仅发字段名+枚举值列表+用户输入 | 实现时沿用 Phase 2 L2 的 LLM 治理模式（结构化信号、不下发原始业务行、调用日志）；若需要独立治理规则再补 | 实现者 | 枚举标准化器开发时 |
| P2 | Phase 4 依赖未实现的 Phase 5/6 契约 | Phase 4 实现/验证 | NormalizedValue 的接口设计可能需在 Phase 5/6 落地时调整；Phase 4 独立测试只能覆盖策略链+mock，无法验证「Phase 5 字段识别→ Phase 4 标准化→ Phase 6 SQL 生成」的端到端闭环 | `src/normalizer/` 为空；Phase 5/6 尚未进入规格 | PRD 显式定义 Phase 4→5 和 Phase 4→6 的接口契约（NormalizedValue 数据结构 + 函数签名）；Phase 4 单测覆盖所有策略链 + mock 字段上下文；端到端验证标为 Phase 5 联调 gate | @yanheng | Phase 5 规格时 |
| P2 | 名称 LIKE 回退引入目标库读路径 | 名称 7 策略全失败 | Phase 4 标准化逻辑新增对目标业务库的 `LIKE` 查询——与 Phase 2 FK 推断/模式检测一样的 `query_executor` 模式，但 Phase 4 在用户查询的**热路径**上使用，超时/限流/权限需明确定义 | refine 写了 `SELECT DISTINCT ... LIKE ... LIMIT 10`，但未定义超时（statement_timeout？）、并发限制（与准实时查询竞争） | PRD 定义目标库 LIKE 查询的参数（超时、statement_timeout、限流）；复用 Phase 2 `query_executor` + `SET TRANSACTION READ ONLY` | 实现者 | 名称标准化器开发时 |
| P2 | 值映射中心 CRUD API 范围未定 | 管理员批量导入/维护映射 | 映射存储 CRUD 的粒度（单条增删改 vs 批量导入 | refine 说「CRUD API」但未列出端点 | PRD 定义最小 CRUD：POST/GET/DELETE 枚举别名、区域字典、名称简称的单条 + 批量导入 | @yanheng | 进 PRD 前 |
| P2 | 区域种子 CSV 来源与格式未定 | 首次激活数据源 | 无法自动导入；管理员无区域数据可用 | refine 说「中国行政区划 CSV」但未指定格式/来源 | PRD 选一个明确格式（如 3 列：province/city/district + parent_code），标注从哪获取（内置、开源数据集或 Ops 提供） | @yanheng | 进 PRD 前 |
| P2 | Phase 4 无法端到端验证（依赖 Phase 5/6） | 测试验收 | 开发完成后所有测试都是 mock 的 Phase 5/6 接口，无法证明「用户输入→SQL 的完整链路」正确 | src/normalizer/ 空；Phase 5/6 代码不存在 | 单测覆盖全部策略链（纯函数 + mock 字段上下文）；端到端验证标 Phase 5 联调 gate；手工验收可用脚本注入 mock 字段上下文 | 实现者 | Phase 5 联调时 |
| P3 | NormalizedValue 数据结构未在 refine 中复述 | 实现期查阅 | 需回跳设计文档 §4.1 找定义 | refine 引用了设计文档但不含 struct 定义 | PRD 补全 `NormalizedValue` 的 field 定义 | — | PRD 时 |
| P3 | 固定日期周期预设列表未确认 | 时间标准化 | 双十一/618 等需有一个明确初始列表 | refine 说「代码常量+CRUD」但未列初始值 | PRD 列出 V1 预设列表（双十一/618/春节？等） | @yanheng | PRD 时 |
| P3 | 各策略链的阈值（编辑距离 0.7、LLM confidence 0.85）调优未经验证 | 上线后 | 阈值过高→命中率低、过低→误匹配 | 设计文档给了默认值但无实证 | V1 用设计文档默认值；Phase 5 联调时收集命中率数据、迭代调优 | — | Phase 5 联调后 |

## 需要补充的问题

1. 名称 LIKE 回退的目标库连接参数（超时/限流）需在 PRD 中定义（P2，不阻塞 PRD 固化）。
2. 区域种子 CSV 的具体格式（列名、分隔符、层级编码规则）需在 PRD 中指定。
3. 固定日期周期的 V1 预设列表（双十一 / 618 是否唯一？要否春节/国庆？）。

（均为 P2/P3，不阻塞 PRD 固化；可在 `team-spec-to-prd` 直接补入。）

## 建议改写（供 PRD 固化时补入，不改 refine.md）

无需改写 refine.md。建议 PRD 固化时补：
- **接口契约**（补 P2 Phase 5/6 依赖）：显式定义 Phase 4 的输入（`field_context = {table, column}` + `raw_value`）和输出 `NormalizedValue` 的结构。
- **名称 LIKE 回退参数**：超时（statement_timeout）、限流（与并发查询的隔离）、复用的 query_executor 模式。
- **值映射中心数据模型**：枚举别名表、区域字典表、名称简称表的 schema（列 + 约束）。
- **区域 CSV 格式**：指定列和分隔符（如 `parent_code,level,name`），标注来源（项目内置文件或管理界面上传）。
- **固定日期周期预设**：列出 V1 初始值（双十一、618、春节等）。

## Change Log

- 2026-06-19：首次评审。对照设计文档 IV、Phase 2/3 先例、代码现状（`src/normalizer/` 空）核验。5 轮细化决议完整、验收口径可观察。无 P0、P1 仅 LLM 治理（已有 Phase 2 先例接受）；5 项 P2（Phase 5/6 契约依赖、LIKE 目标库读、CRUD 范围、区域 CSV 来源、集成验证 gated）+ 3 项 P3。结论 `ready`，可进 PRD。
