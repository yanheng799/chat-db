# 规格评审 — 元数据学习（Phase 2）

- **slug**：`2026-06-14-metadata-learning`
- **最新评审日期**：2026-06-19（第二轮复查）
- **评审对象**：`spec/refine.md`（第二轮 review-driven 修订版）+ `spec/decisions/0001-fk-inference-in-learning.md`
- **评审依据**：设计文档 §七、开发计划 Phase 2、`src/learning/orchestrator.py`、`src/learning/l2_inference.py`、`src/config/settings.py`、`src/api/datasources.py`
- **Status**：`ready`（首轮 4 个 P1 已全部闭合并经代码核验；残余为 P2/P3，可在 PRD/issue 阶段跟踪）

---

## 第二轮复查结论（2026-06-19）

首轮标 `needs refinement` 的 4 个 P1 阻塞项已在第二轮 `refine.md` 中逐项闭合，本次逐一对照代码核验，闭合成立。无 P0，无新增 P1 阻塞。可进入 PRD 固化，残余 P2/P3 在 PRD/issue 阶段跟踪。最大残余风险来自**测试与验收**维度——覆盖率口径修复（Issue B）与 L2 并发/治理修复（Issue C）存在耦合：单独修 B 会暴露 L2 在默认并发下的静默失效，需注意 issue 落地顺序。

### 首轮 P1 闭合核验（对照代码）

| 首轮 P1 | 第二轮闭合方式 | 代码核验 | 结论 |
|---|---|---|---|
| 覆盖率口径失真 | 改为 `semantic_description` 非空占比；代码 bug 拆独立 Issue B | `orchestrator.py:261`（`l1_count = l1_split + l1_pattern`）、`:271`（`columns_described = l0+l1+l2`）、`:274`（`≥0.8→success`）；模式检测对每列写 `null_ratio`（`:193-196`）使 `l1_pattern_count≈total_columns` → 比值恒 ≥0.8 甚至 >100%。bug 属实，修法方向正确 | ✅ 闭合 |
| L2 采样数据外发 | 新增「数据治理」章节：V1 不下发任何原始行（仅结构化信号），记为 V1 偏差，Phase 10 受控重评估；改 L2 落 Issue C | `l2_inference.py:60-82`（`build_sample_query` 仍 `LIMIT 5`）、`:89-130`（system+user prompt 含「样本数据」块）、`orchestrator.py:407-421`（取样并传入 `call_llm_with_retry`）。外发属实，治理口径已定 | ✅ 闭合 |
| L2 默认并发 5 共享 AsyncSession | 写入「AsyncSession 单任务安全」不变式；改 session factory + 每表独立 session 落 Issue C | `orchestrator.py:351-454`（单 `session` 入参 + `gather` + `Semaphore`）、`:266-269`（`suppress(Exception)` 包 L2，失败静默吞掉）。并发违规属实，修法方向正确 | ✅ 闭合 |
| FK 推断阈值/存储/owner 未定 | 钉：新表 `metadata_inferred_fks`、重叠率≥0.8、名称相似度门槛 0.5、置信度映射（≥0.95→0.8 / 0.8–0.95→0.65）、`source=rule_inference`、owner @yanheng；决策 0001 记录 | `src/learning` 无 FK 推断代码、`metadata_foreign_keys` 无 confidence/source（与缺口描述一致）。参数已钉死，PRD 可据此拆 issue | ✅ 闭合 |

### 风险清单（第二轮）

| 等级 | 风险 | 触发条件 | 影响 | 证据/缺口 | 建议动作 | Owner | 截止点 |
|---|---|---|---|---|---|---|---|
| P2 | Issue B 与 Issue C 耦合：单修覆盖率口径会暴露 L2 静默失效 | 先合并 B 后合并 C | 大量学习日志从 `success`（失真）翻为 `partial_success`/`failed`，运营误判为回归 | B 修真实覆盖率；C 修前 L2 在默认并发 5 共享 session 下大概率静默 no-op（`orchestrator.py:266-269` suppress 吞错） | PRD/issue 排期让 C 先于或同批于 B 落地；B 的验收在 C 生效后复跑 | @yanheng | 拆 issue 时 |
| P2 | 推断外键重跑语义未定 | 手动重跑 `run_learning` | Issue A 验收歧义：重跑是「重算替换」「fill-once 保留」还是「upsert」未指定，可能返工 | refine 对 `semantic_description` 明确 fill-once，对 `metadata_inferred_fks` 重跑行为只字未提 | refine/PRD 补一句：推断外键每次重算替换（纯 SQL 聚合，新鲜度优先）；若需保留人工修正另立字段 | @yanheng | 进 PRD 前 |
| P2 | partial_success/failed 无运营处置（首轮 P2 未闭合） | 学习未达 80% 覆盖或失败 | 无人知晓、不重试、无告警 | refine 仅定义状态枚举，未给监控/告警/重试动作 | PRD 注明监控/告警延 Phase 11，V1 仅记日志 + 管理端可查 learning-logs | @yanheng | 进 PRD 前 |
| P2 | V1 不下发原始行可能拉低 L2 覆盖率 | 含 `usr_typ_cd` 类无注释、拆词失败的列 | 仅靠字段名+类型+枚举+注释，L2 命中率下降，部分 schema 难达 80% → 普遍 partial_success | V1 偏差代价未量化；与上一条运营处置耦合 | PRD 明确 V1 可接受覆盖率下限与 partial_success 属预期；Phase 10 治理就绪后重评采样 | @yanheng | 进 PRD 前 |
| P2 | L2 并发安全缺运行期测试 | 默认并发 5 | Issue C 若只改结构不补并发>1 的真实 AsyncSession 测试，回归不可见 | 现有 L2 测试通过但运行期并发行为「Unclear」（首轮遗留） | Issue C 验收加一条：并发>1 跑 L2 不触发 AsyncSession 并发错误 | Issue C 实现者 | C 开发时 |
| P3 | `learning_l2_max_calls` 默认值（建议 200）未确认 | 大 schema | 默认过小→提前停 L2；过大→成本失控 | refine 开放问题 2，无 owner 确认；`settings.py` 现无该项 | 实现时定 200（0=不限），PRD 备注可配 | @yanheng | C 开发时 |
| P3 | `run_learning` docstring 过时 [D2] | 维护阅读 | 声称 L1/L2 占位，实际已实现，误导 | `orchestrator.py:218-222` | Issue A 顺手修（refine 已记） | Issue A 实现者 | A 开发时 |
| P3 | fill-once 改注释不刷新 [D1] | 管理员事后改库注释 | 旧描述不更新 | refine 已记为已知限制 | 保持现状，文档说明 | — | — |
| P3 | sync→learning 未接（首轮 P2，已转为开放问题） | schema 同步新增列 | 新列保持未描述直到手动重跑 | 仅 `datasources.py:301`（首次提取后 auto）、`:701`（manual）触发；同步引擎无 learning 调用——与 refine 开放问题 1 描述一致 | V1 不接，Phase 7/11 再评；PRD 显式列为已知限制 | @yanheng | — |

### 需要补充的问题（第二轮）

1. 推断外键重跑语义定「重算替换」是否可接受？（纯 SQL 聚合，新鲜度优先于稳定性，推荐）
2. V1 可接受的覆盖率下限是多少？partial_success 是否视为 V1 预期（而非告警）？
3. Issue B/C 是否同批或 C 先落地，避免覆盖率修复单独暴露 L2 静默失效？

### 建议改写（不阻塞进入 PRD，建议在 PRD 固化时补入）

无需改写 `refine.md` 现有章节（首轮 4 个 P1 已闭合）。建议在 PRD 固化时补三处：
- **编排与来源标记**：补一句「推断外键（`metadata_inferred_fks`）每次学习重算替换，不适用 fill-once」。
- **覆盖率判定**：补「V1 因不下发原始行，含大量无注释列的 schema 可能普遍 partial_success，属预期；监控/告警延 Phase 11」。
- **后续 issue 排期**：标注「C 先于或同批于 B」。

### 下一步可选

见本评审最终回复（Status: `ready`，选项 1 为 `team-spec-to-prd`）。

---

## 首轮评审（2026-06-14，历史保留）

> 以下为首轮评审原文。首轮标 `needs refinement` 并提出 4 个 P1，已全部在第二轮闭合（见上方「第二轮复查」）。保留作历史溯源。

### 结论

不 ready 进入 PRD 固化。存在 4 个 P1 阻塞项：L2 把采样的业务数据原样发给外部 LLM 无任何数据治理；refine.md 的覆盖率验收口径照搬了代码里失真的 `columns_described`（几乎恒判 success）；L2 默认并发 5 共享 AsyncSession，违反 SQLAlchemy 单任务约束且失败被静默吞掉，L2 可能在默认配置下静默失效；FK 推断缺口的阈值/存储/owner 均未定，PRD 无法据此拆 issue。最大风险来自**测试与验收**（覆盖率口径失真）与**权限合规**（L2 数据外发）两个维度。

### 阻塞项

| 等级 | 阻塞项 | 为什么阻塞 | 建议动作 | Owner | 截止点 |
|---|---|---|---|---|---|
| P1 | 覆盖率验收口径失真 | 代码 `columns_described` 含 `l1_pattern_count`（模式检测给每列写 `null_ratio`，≈total_columns），并可与 L0 双计，`/total_columns` 几乎恒 ≥0.8；refine.md「≥80%→success」照搬此逻辑，验收基线不可信 | refine 把覆盖率重定义为「`semantic_description` 非空列占比」，代码现状记为偏差/bug，随 FK issue 或独立 issue 修 | 规格作者 | 进入 PRD 前 |
| P1 | L2 采样数据外发外部 LLM 无数据治理 | 业务库每表采样 5 行原样发 DashScope（第三方），含潜在 PII/敏感数据；spec/PRD 未定义可采样范围与脱敏规则，存在合规风险 | refine 新增「数据治理」章节：敏感列 denylist / 管理员可配采样策略 / 明确 V1 假设 | 规格作者 | 进入 PRD 前 |
| P1 | L2 默认并发 5 共享 AsyncSession | `run_l2_inference` 用 `asyncio.gather` 让多表并发用同一 session，SQLAlchemy AsyncSession 禁止跨任务并发；且 `run_learning` 用 `contextlib.suppress(Exception)` 包 L2 → 失败被静默吞掉，L2 可能在默认配置下静默 no-op | refine 把「AsyncSession 单任务安全」写成 L2 不变式，标注当前默认并发 5 + 共享 session 需在 issue 中验证/修正（每表独立 session 或串行） | 规格作者（写不变式）+ L2 issue 实现者 | 进入 PRD 前 / L2 issue 开发前 |
| P1 | FK 推断阈值/存储/owner 未定 | PRD 要据此拆 issue，但重叠率阈值、名称相似度权重、推断外键存储（扩表/新表）、owner 全空 | refine 至少钉默认阈值（重叠率≥0.8）+ 存储倾向 + owner；或显式声明「issue 阶段定」并给判定标准 | 规格作者 | 进入 PRD 前 |

### 风险清单

| 等级 | 风险 | 触发条件 | 影响 | 证据/缺口 | 建议动作 | Owner | 截止点 |
|---|---|---|---|---|---|---|---|
| P1 | 覆盖率口径失真 | 每次学习 | success/partial 判定错误，运营误判学习质量 | `orchestrator.py:271` columns_described 含 l1_pattern_count；模式检测对每列写 null_ratio | 重定义覆盖率 + 标 bug | 规格作者 | PRD 前 |
| P1 | L2 数据外发合规 | 目标库含 PII/敏感数据 | 数据泄露、合规违规 | `l2_inference.py` 仅排除 BLOB/截断 TEXT，无脱敏；数据敏感性未确认（Unclear） | refine 加数据治理规则 | 规格作者 | PRD 前 |
| P1 | L2 并发违反 AsyncSession 约束 | 默认 `max_concurrency=5` | L2 报错被静默 → L2 静默失效 | `settings.py:66` 默认 5；`run_l2_inference` gather 共享 session；测试通过但运行期行为未验证（Unclear） | 验证运行期；refine 写不变式；issue 改 | 规格作者 + L2 issue 实现者 | PRD 前 / L2 issue 开发前 |
| P1 | FK 阈值/存储/owner 未定 | 拆 FK issue 时 | PRD/issue 无法启动 | refine「开放问题 1/2」无 owner 无默认 | 钉默认 + owner | 规格作者 | PRD 前 |
| P2 | 无 LLM 成本上限 | 大 schema（数百表，整表一次 prompt） | 调用失控、成本超支 | 只有并发(5)+超时(60min)，无 max_calls/预算 | refine/PRD 加表数上限或成本预算 | 规格作者 | PRD 前 |
| P2 | partial_success/failed 无运营处置 | 学习失败或部分覆盖 | 无人知晓、不重试、无告警 | spec 只定义状态枚举无后续动作 | refine 注明监控延 Phase 11，或定义最小告警 | 规格作者 | PRD 前 |
| P2 | 「同步触发重学习」未验证 | 元数据同步后 | 新列可能不被描述（与 fill-once 声明耦合） | refine 假设 sync 后会跑 run_learning；issue #12 实际链路未核 | 核实 sync→learning 触发链路 | 规格作者 | PRD 前 |
| P3 | fill-once 改注释不刷新 | 管理员事后改库注释 | 旧描述不更新 | 已记为已知限制（[D1]） | 保持现状，记录即可 | — | — |
| P3 | `run_learning` docstring 过时 | 阅读/维护时 | 误导（声称 L1/L2 占位） | 已记为偏差（[D2]） | FK issue 顺手修 | issue 实现者 | 开发时 |

### 需要补充的问题

1. 覆盖率：是否确认「success = `semantic_description` 非空列占比 ≥80%」？代码 bug 是否纳入本期 FK issue 一起修，还是独立 issue？
2. L2 数据治理：V1 是否假设目标库非敏感？要不要敏感列 denylist / 脱敏 / 管理员可配采样范围？
3. L2 并发：是否需要本期确认 AsyncSession 并发安全（运行期验证默认 5）？修法倾向每表独立 session 还是串行？
4. FK 推断：重叠率阈值默认（建议 0.8）、名称相似度权重、推断外键存储（扩 `MetadataForeignKey` / 新表）、owner 分别怎么定？
5. LLM 成本：是否需要表数上限或单次学习调用预算？

### Questions For User（回到 team-spec-refine 确认）

1. L2 采样外发的数据治理口径怎么定？（非敏感假设 / denylist / 脱敏 / 管理员可配，四选一或多）
2. 覆盖率验收口径改为「`semantic_description` 非空占比」，代码 bug 归 FK issue 还是独立 issue？
3. L2 并发安全是否本期定为不变式并修？修法倾向？
4. FK 推断的默认阈值、存储形态、owner 怎么钉？

### Required Refinement（需更新 `spec/refine.md` 的章节）

- **新增「数据治理 / 隐私」章节**：L2 采样外发规则（脱敏/denylist/可配/非敏感假设之一）。
- **修正「验收口径」与「编排与来源标记」的覆盖率定义**：改为 `semantic_description` 非空列占比；把代码 `columns_described` 计法记为偏差/bug，明确归属 issue。
- **L2 章节加不变式**：并发必须保证 AsyncSession 单任务安全；标注默认并发 5 + 共享 session 需验证/修正。
- **「后续 issue 草稿」FK 部分**：钉默认阈值（重叠率≥0.8）+ 存储倾向 + owner。
- **「开放问题」补**：LLM 成本上限、partial/failed 运营处置、sync→learning 触发链路核验。
- **「风险扫尾」升级**：把覆盖率口径、L2 数据外发、L2 并发三项从隐性提升为显式 P1。

### 建议改写（覆盖率口径）

把 refine.md 现有：

> 覆盖率判定：`columns_described / total_columns ≥ 0.8` → `success`；`>0` → `partial_success`；`0` → `failed`。

改写为：

> 覆盖率 = 该数据源下 `semantic_description` 非空的列数 / 总列数。
> ≥0.8 → `success`；>0 → `partial_success`；=0 → `failed`。
> **当前实现偏差（bug）**：`columns_described` 把模式检测写入 `null_ratio` 的列也计入（≈全表），并与 L0 双计，使该比值几乎恒 ≥0.8、甚至 >100%，`success` 判定失效。需在 issue 中改为按 `semantic_description IS NOT NULL` 统计；归属：FK 推断 issue 或独立修复 issue（待定，见开放问题 1）。

## Change Log

- 2026-06-14：首轮评审。发现 4 个 P1（覆盖率口径失真、L2 数据外发合规、L2 AsyncSession 并发、FK 阈值/owner 未定），结论 `needs refinement`，建议回 `team-spec-refine` 修正后再进 PRD。
- 2026-06-19：第二轮复查。逐项对照代码核验，首轮 4 个 P1 全部闭合；无 P0、无新增 P1；残余 5 项 P2（B/C 耦合、推断外键重跑语义、partial/failed 运营处置、V1 覆盖率预期、L2 并发运行期测试）与 4 项 P3，均可进 PRD 后跟踪。结论 `ready`。
