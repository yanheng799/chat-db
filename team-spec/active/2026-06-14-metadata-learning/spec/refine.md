# 元数据学习（Phase 2）— 规格细化

- **slug**：`2026-06-14-metadata-learning`
- **状态**：refining（第二轮，review-driven 修订完成，待 `team-spec-review` 复查）
- **基线**：设计文档 §七 元数据学习系统 + 开发计划 Phase 2（2.1–2.4）
- **细化模式**：全量事后规格 + 差距标注。Phase 2 代码已大半实现，本规格以设计基线为锚，完整描述 L0–L2 预期行为，审计当前代码并标注「已建 / 缺口 / 偏差」，缺口落为后续 issue。
- **关联决策**：[0001 值重叠度外键推断归属 Phase 2 learning](./decisions/0001-fk-inference-in-learning.md)
- **关联评审**：[reviews.md](./reviews.md)（首轮标 `needs refinement`，本轮已逐项闭合 4 个 P1）

## 需求复述

系统需要为已提取的元数据（表、字段）自动产出**带来源标注的语义描述**和**推断关系（外键）**，供下游语义匹配、SQL 生成、图谱 JOIN 路径发现使用。Phase 2 用四层递进架构（L0–L3）逐步提升覆盖率，V1 实现 L0–L2 的脱机批量学习，L3 人工补充留到 Phase 10 管理端。

## 问题与价值

- **痛点**：Phase 1 只提取了结构元数据（表/字段/索引/显式外键），没有「这个字段在业务上是什么意思」「这两张表怎么关联」的语义层。没有它，Phase 5 语义匹配无法把用户口语映射到字段，Phase 6 多步查询无法发现 JOIN 路径。
- **价值**：每列/每表都有来源可追溯的语义描述；推断外键补齐未声明的表关系（尤其 MySQL 业务库普遍不声明外键），让下游 JOIN 发现可用。
- **触发**：数据源激活并完成首次元数据提取后**自动触发**（`trigger_type=auto`）；管理员可**手动触发**（`trigger_type=manual`）。**注意：schema 同步（diff）不触发学习**（见「编排」节）。

## 用户与场景

1. 作为**系统（auto）**，数据源首次提取完成后自动跑 L0→L1→L2，给每列/每表补语义描述。
2. 作为**管理员（manual）**，在 schema 变更或描述质量不满意时，手动重跑学习。
3. 作为**下游系统**（Phase 3 图谱 / Phase 5 语义匹配），读取带 `source` 与 `confidence` 的语义描述与推断外键。

## 术语

| 术语 | 定义 |
|------|------|
| 语义描述（semantic_description） | 表/字段在业务上的中文含义，由 L0–L2 产出。 |
| 来源标记（source） | `semantic_description` 的溯源，取值 `schema_comment` / `rule_inference` / `llm_inference`。 |
| 置信度（confidence） | 语义描述的可信分值，L0=1.0、L1=0.7、L2=0.5（FK 推断按重叠率映射，见 L1）。 |
| 已覆盖 / 未覆盖列 | `semantic_description` 是否为空。学习只填充未覆盖列。 |
| 显式外键 | 目标库 `information_schema` 里声明的外键，Phase 1 已提取，存 `metadata_foreign_keys`。 |
| 推断外键 | 由字段名相似度 + 值重叠率推断的潜在表关系（Phase 2 缺口），存新表 `metadata_inferred_fks`。 |
| 值重叠度 | 跨表两个字段值集合的重叠比例，用于推断外键。 |

## 范围内

- L0：从库注释提取语义描述（`source=schema_comment`）。
- L1：字段名拆词（`source=rule_inference`）。
- L1：数据模式检测（枚举值、NULL 比例、数值范围）。
- L1：**值重叠度外键推断**（`source=rule_inference`）—— **当前为缺口，见后续 issue A**。
- L2：LLM 语义推断（脱机批量、并发与成本控制，**不下发原始采样行**，`source=llm_inference`）。
- 编排：L0→L1→L2 串联，来源标记与置信度，覆盖率统计与学习日志。
- 重跑覆盖语义：fill-once（只填未覆盖列，已有描述不刷新）。

## 范围外

- **L3 人工补充**（图谱可视化确认界面）—— 延期到 Phase 10。
- 向量库 / 图谱构建（Phase 3）。
- 值映射、热词词典（Phase 3）。
- **V1 不向外部 LLM 外发任何原始采样行**（见「数据治理」；Phase 10 治理框架就绪后受控重评估）。
- 重跑时按置信度重新评估/升级已有描述（[D1]，记为已知限制）。
- **schema 同步自动触发重学习**（当前不接；是否接见「开放问题」）。
- 字段名拆词词表扩充维护（运营事项）。

## 数据治理 / 隐私（V1 原则）

- **V1 学习链路不向外部 LLM（DashScope）外发任何原始业务数据行。** L2 仅用结构化信号推断：字段名 + 数据类型 + L1 枚举值 + L0 注释 + 拆词结果。
- **依据**：V1 无数据治理框架（无管理端 UI、无审计、无授权流），denylist/脱敏都是「尽力而为」——漏判即泄漏，合规上难交代；而 L1 已提供强信号（枚举值/空值率/数值范围/拆词）+ L0 注释，原始行的边际价值低。
- **偏差**：与设计 §七 L2「采样数据」输入偏离，记为 V1 偏差。Phase 10 治理框架（管理端 + 审计 + 可配采样策略/敏感列）就绪后，在受控前提下重新评估开放采样。
- **代码现状**：`l2_inference.py` 仍含 `build_sample_query` + prompt 样本块；需在 L2 issue（C）中改为不下发原始行。

## 行为规格

### L0 — Schema 注释提取

- 遍历激活数据源的所有表与字段。
- 表/列若有库注释（`table_comment` / `column_comment`）且 `semantic_description` 为空：写入注释，`source=schema_comment`，`confidence=1.0`。
- 已有描述不覆盖。

### L1 — 规则推断（拆词 + 模式检测 + 外键推断）

L1 有两类输出：

**(a) 语义描述（写入 `semantic_description`，`source=rule_inference`，`confidence=0.7`）**
- **字段名拆词**：对未覆盖列，按 CamelCase / snake_case 拆分，查中英词表翻译。成功则写入；失败留给 L2。

**(b) 结构统计（写入独立字段，不参与 `source`）**
- `detected_enum_values`：列被判为枚举时写入去重值（≤20 个）。
- `null_ratio`：`null_count / total_rows`。
- `numeric_range`：数值列写入 `{min, max}`。
- 模式检测对**所有列**生效（不受是否已覆盖影响），每表一条聚合查询，>100 万行采样（PG `TABLESAMPLE SYSTEM(1)` / MySQL `LIMIT 10000`）。

**(c) 推断外键（缺口，预期行为，存新表 `metadata_inferred_fks`）**
- **候选对生成**：跨表、数据类型匹配、一侧为 PK/unique、字段名相似度 ≥0.5（门槛，低于不进候选）。
- **值重叠率**：连活库算跨表字段值重叠比例，大表复用采样（`query_executor` + `should_use_sampling`）。
- **判定**：重叠率 ≥ **0.8**（默认，可配）→ 产出一条推断外键行。
- **置信度映射**：`overlap≥0.95 → confidence=0.8`；`0.8≤overlap<0.95 → confidence=0.65`；`source=rule_inference`。
- **存储**：新表 `metadata_inferred_fks`（`source_column / target_table / target_column / overlap_rate / name_similarity / confidence / source`），与显式外键 `metadata_foreign_keys` 分离，镜像 §九 图谱 `REFERENCES` vs `INFERRED_REF` 两种边。

### L2 — LLM 语义推断

- 仅处理 L0+L1 后仍未覆盖的列，**整表一次 prompt**（该表所有未覆盖列）。
- **输入（不下发原始行）**：字段名 + 数据类型 + L1 枚举值 + L0 注释 + 拆词结果。**[V1 偏差]** 设计 §七 列「采样数据」为输入，V1 出于数据治理暂不下发（见「数据治理」）。
- LLM 返回 JSON `{字段名: 语义描述}`；解析失败或字段为 null 则该列留空。
- 命中则写入，`source=llm_inference`，`confidence=0.5`。
- **并发不变式**：L2 并发执行时，**每个并发任务必须使用独立的 AsyncSession**。当前实现 `run_l2_inference` 用 `asyncio.gather` 让多表共享同一 session，违反此约束（默认并发 5），且失败被 `run_learning` 的 `suppress(Exception)` 静默吞掉 → 需在 issue（C）中改为接收 session factory、每表独立 session。
- **成本/可靠性控制**：信号量并发（`learning_l2_max_concurrency`，默认 5）、整体超时（`learning_job_timeout_minutes`，默认 60）、**单次学习最大 LLM 调用数（`learning_l2_max_calls`，默认保守 200，超限提前停 L2 + 记日志；0=不限）**、429 指数退避重试 `[2,4,8]s` 共 3 次；非限流错误不重试、记日志。

### 编排与来源标记

- 顺序：L0 → L1 拆词 → L1 模式检测 → L2。L1 模式检测与 L2 失败被抑制，不阻断整体流水线。
- 来源 / 置信度矩阵：

| 来源 | `source` | `confidence` | 触发 |
|------|----------|--------------|------|
| 库注释 | `schema_comment` | 1.0 | L0，有注释且未覆盖 |
| 规则推断 | `rule_inference` | 0.7 | L1 拆词成功 / L1 FK 推断（缺口，置信度按重叠率映射） |
| LLM 推断 | `llm_inference` | 0.5 | L2，L0+L1 未覆盖且 LLM 返回非空 |

- **触发**：首次元数据提取完成后自动触发（`datasources.py` extraction → `_run_learning_auto`）；管理员手动触发。**schema 同步（diff）不触发学习**——同步新增的列保持未描述，直到手动重跑或重新激活。
- **覆盖语义（fill-once）[D1]**：各层只填 `semantic_description is None` 的列，一旦写入永不刷新。改注释或想升级已有描述不会自动刷新——记为已知限制。
- **覆盖率判定**：覆盖率 = 该数据源下 `semantic_description IS NOT NULL` 的列数 / 总列数。`≥0.8 → success`；`>0 → partial_success`；`=0 → failed`。
  - **代码偏差（bug，→ 独立 issue B）**：当前 `columns_described = l0+l1_split+l1_pattern+l2`，其中 `l1_pattern_count` 把模式检测写入 `null_ratio` 的列（≈全表）也计入、并与 L0 双计，使比值几乎恒 ≥0.8、甚至 >100%，`success` 判定失效。需改为按 `semantic_description IS NOT NULL` 统计。
- 学习日志（`MetadataLearningLog`）记录 l0/l1/l2 计数、`l2_llm_calls`、状态、起止时间、错误信息。

## 验收口径

**应通过**：
- 有库注释的列 → `semantic_description`=注释，`source=schema_comment`，`confidence=1.0`。
- 无注释的 `created_at` → L1 拆词得到中文描述，`source=rule_inference`，`confidence=0.7`。
- 枚举列（如 3 个去重值 / 10000 行）→ `detected_enum_values` 填入这 3 个值。
- 数值列 → `numeric_range={min,max}`；含 NULL 列 → `null_ratio` 正确。
- L0+L1 都搞不定的列（如 `usr_typ_cd`）→ L2 用结构化信号推断，`source=llm_inference`；**不下发原始行**。
- 覆盖率（按 `semantic_description` 非空）≥80% → `status=success`。
- 大表（>100 万行）模式检测走采样，不 OOM、不超时。
- L2 并发跑多表（默认 5）不触发 AsyncSession 并发错误，每表独立 session。

**应失败 / 边界**：
- 1000 去重值 / 1000 行的列 → 比例 1.0，**不**判为枚举。
- 25 去重值 / 10000 行 → 比例 <0.05 但 >20，**不**判为枚举（违反 ≤20）。
- 空表（total_rows=0）→ 不判枚举、不写 `null_ratio`。
- L2 整表调用返回非法 JSON → 该表列保持未覆盖，不抛错、不阻断。
- LLM 限流耗尽重试 → 该表返回 None，流水线继续。
- LLM 调用数达 `learning_l2_max_calls` → 提前停 L2、记日志、流水线仍算 success/partial（按已覆盖）。

**外键推断验收（缺口，待 issue A 落地）**：
- `orders.customer_id` 与 `customers.id`：类型匹配、`customers.id` 为 PK、名称相似度 ≥0.5、重叠率 ≥0.8 → 产出一条 `metadata_inferred_fks` 行，`confidence` 按重叠率映射，`source=rule_inference`。
- 重叠率 <0.8 或名称相似度 <0.5 的列对 → 不产出。

## 审计结论（已建 / 缺口 / 偏差）

| 项 | 状态 | 说明 |
|----|------|------|
| L0 注释提取 | ✅ 已建 | `orchestrator.run_l0`，符合设计。 |
| L1 字段名拆词 | ✅ 已建 | `splitter.py` + `word_table.py` + `run_l1_splitting`。 |
| L1 数据模式检测 | ✅ 已建 | `pattern_detector.py` + `run_l1_pattern_detection`，含采样。 |
| **L1 值重叠外键推断** | ❌ **缺口** | 设计 §七 + 开发计划 2.2 要求，代码与数据模型均无。→ issue A（新表 `metadata_inferred_fks`）。 |
| L2 LLM 语义推断 | ⚠️ 已建 + 2 处偏差 | 采样/重试/并发/超时已建；但 (1) 当前下发原始采样行，V1 应改为不下发（数据治理）；(2) 共享 session 并发违反 AsyncSession 约束。→ issue C。 |
| 编排 + 来源标记 | ✅ 已建 | `run_learning`，三层来源与置信度齐全。 |
| 覆盖率 metric | ⚠️ bug | `columns_described` 含 pattern 计数，success 判定失效。→ issue B。 |
| L2 成本上限 | ❌ 缺口 | 无 `max_calls` 上限。→ issue C 补 `learning_l2_max_calls`。 |
| sync→learning | ⚠️ 未接 | 同步不触发学习，新增列不自动描述。→ 开放问题。 |
| 覆盖语义 | ⚠️ 偏差 [D1] | fill-once，接受为 V1。 |
| `run_learning` docstring | ⚠️ 偏差 [D2] | 声称 L1/L2 占位，实际已实现。顺手修。 |
| L3 人工补充 | ⏭️ 范围外 | 延期 Phase 10，符合设计。 |

## 开放问题

1. **sync→learning 是否对新增列接上自动重跑？** 现状不接（同步新增列保持未描述直到手动重跑）。接上会引入"同步后异步重学"的复杂度与 staleness 交互。建议 V1 不接、文档明确，Phase 7/11 再评估。
2. **`learning_l2_max_calls` 默认值**（建议 200）是否合适？需结合典型 schema 规模定。
3. **采样何时受控重新开放**：Phase 10 治理框架（管理端 + 审计 + 可配敏感列/采样策略）就绪后再评估。

## 轻量风险扫尾

- **P1 已闭合（本轮）**：覆盖率口径（改写 + issue B）、L2 数据治理（不发原始行 + issue C）、L2 并发安全（不变式 + 每表独立 session + issue C）、FK 阈值/存储/owner（钉死 + issue A）。
- **残留 P2**：sync→learning 未接——新增列不自动描述，记为开放问题 1，是否接由产品定。
- **P3**：fill-once 改注释不刷新（[D1]，已知限制）；`run_learning` docstring 过时（[D2]，顺手修）。
- **无 P0 阻塞**：主路径 L0–L2 已建且符合设计，规格可进入 review 复查。

## 后续 issue 草稿

供 `team-prd-to-issues` / `team-issue-implement` 派生：

- **Issue A — 值重叠度外键推断（owner: @yanheng）**：新表 `metadata_inferred_fks` + Alembic 迁移；候选对生成（类型匹配 + PK/unique + 名称相似度≥0.5 门槛）；值重叠率查询（复用 `query_executor` + 采样）；判定（重叠率≥0.8）+ 置信度映射 + `source=rule_inference`；接入 `run_learning` 作为 L1 子步骤，失败不阻断；顺手修 [D2] docstring。
- **Issue B — 覆盖率 metric 修复（独立小 issue）**：`columns_described` 改按 `semantic_description IS NOT NULL` 统计；修正 `l1_count` 语义（拆词与模式检测分别计，模式检测不计入"已描述"）。
- **Issue C — L2 治理 + 并发安全 + 成本上限**：L2 prompt 改为不下发原始采样行（仅结构化信号）；`run_l2_inference` 入参改 session factory、每表独立 AsyncSession；新增 `learning_l2_max_calls` 配置与提前停逻辑。

## Change Log

- 2026-06-14（首轮）：确认方向为「全量事后规格 + 差距标注」；审计 learning 代码，确认 [G1] FK 推断为缺口并决定纳入范围（决策 0001）；确认 [D1] 接受 fill-once。
- 2026-06-14（第二轮，review-driven）：闭合 reviews.md 的 4 个 P1 —— (P1.2) L2 数据治理定 D 不发原始采样行，新增「数据治理」章节；(P1.1) 覆盖率口径改 `semantic_description` 非空占比，metric bug 拆 issue B；(P1.3) L2 写 AsyncSession 单任务安全不变式 + 每表独立 session 修法，落 issue C；(P1.4) FK 推断存储定新表 `metadata_inferred_fks`、阈值 0.8、名称相似度门槛 0.5、置信度映射、owner @yanheng。另：核验发现 sync→learning 未接并修正描述（开放问题 1）；新增 `learning_l2_max_calls` 成本上限；后续 issue 拆为 A/B/C 三项。
