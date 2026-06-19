# STATUS

状态：issues-published（6 个 issue 已发布到 GitHub Issues #23–#28，待实现）

- 2026-06-19：`team-spec-refine` 5 轮，确认：
  - 范围 = 收编 3.5 值映射中心（枚举别名 + 区域字典 + 名称简称） + 4.1–4.6 全含；3.4 热词词典继续独立。
  - 流程/接口 = 后置为主 + 时间可前置 + NormalizedValue 由 Phase 6 消费。
  - 数据隔离 = 全三表按 `data_source_id` 隔离 + 区域有全局种子可导入。
  - 失败/追问 = 统一 `need_confirm` + Phase 6 批量追问 + 枚举 LLM 不下发原始行 + 名称 LIKE 回退目标库。
  - 种子数据 = 枚举自动采集 `detected_enum_values` + 区域预置 CSV 自动导入 + 名称手工 + 固定日期代码常量+CRUD。
- 延期项：3.4 热词词典（→ Phase 3.b 或 Phase 5 前置）；区域种子数据具体格式（实现期定）；名称策略权重调优（待语料）。
- 2026-06-19（评审）：`team-spec-review` 核验——无 P0、P1 LLM 治理已接受（Phase 2 先例）、5 项 P2 + 3 项 P3。结论 `ready`。
- 2026-06-19（PRD 固化）：基于 `Status: ready` 的 review 生成 `prd/prd.md`；吸收 review 建议（NormalizedValue 契约、LIKE 回退参数、3 映射表 schema、区域 CSV 格式、固定日期预设）；预拆 A-F 六 issue。
- 下一步：`team-prd-to-issues` 拆工程 issue（建议顺序 A/F 并行 → B/C/D/E 并行）。
- 2026-06-19（拆 issue）：生成 6 个本地 AFK issue 草稿——`001` NormalizedValue+时间、`002` 值映射中心 CRUD（F）、`003` 枚举标准化器（B，依赖 #2）、`004` 区域标准化器（C，依赖 #2）、`005` 名称标准化器（D，依赖 #2）、`006` 数值量词检测（E）。无硬依赖：001/002/006 并行 → 003/004/005 并行。
- 下一步：`team-issue-batch-implement`（按 001/002/006→003/004/005 连续实现）或 `team-issue-publish-github`（发布到 GitHub Issues 跟踪）。
