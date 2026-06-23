# 历史会话持久化 — 规格评审

- **slug**：`2026-06-23-conversation-history-persistence`
- **最新状态**：`ready`（第 2 轮复查，2026-06-23）

---

## 复查（第 2 轮，2026-06-23）

- **评审对象**：`team-spec/active/2026-06-23-conversation-history-persistence/spec/refine.md`（第 2 轮，已回填第 1 轮反馈）
- **Status**：`ready`

### 结论

可进入 PRD 固化。无阻塞项——第 1 轮的 4 项阻塞（保留兜底机制、删除语义、可见性/脱敏、双写同步性）已全部解决或由需求方明确接受。最大残留风险来自**发布与运营维度**：仅手动清理 + 全量无上限，增长仅靠人工删除控制（已接受，scope-conditional）。

### 阻塞项

无 P0 / 必须立即处理的 P1。第 1 轮阻塞处置：

| 原阻塞（第 1 轮） | 处置 | 现状 |
|---|---|---|
| P0 保留兜底机制欠定义 | 需求方选"仅手动清理"，明确接受增长靠人工控制、不做自动任务 | 已接受 → 跟踪项 R1 |
| P1 删除语义未定 | hard delete + 级联 `conversation_summaries`，无 `deleted_at` | 已解决 |
| P1 可见性 / 脱敏未定 | 全局可见 + 不脱敏（接受）；"默认 admin/无门禁"记入全局 CONTEXT | 已解决（合规风险已接受，R2） |
| P1 双写同步性未定 | 异步 fire-and-forget，不阻塞热路径，失败仅记日志 | 已解决 |

### 风险清单（当前）

| 编号 | 等级 | 风险 | 触发条件 | 影响 | 证据/缺口 | 建议动作 | Owner | 截止点 |
|---|---|---|---|---|---|---|---|---|
| R1 | P1（已接受） | 仅手动清理 + 全量无上限 → 增长仅靠人工删除控制 | 实际持续使用且无人定期删除 | 应用库无限膨胀、回看/列表性能退化 | refine §行为规格4、§风险 P1-残留；需求方明确接受 | PRD 写明"仅手动清理、无自动任务"为有意决策；预留"自动保留期清理"为后续可选 issue；部署规模/敏感度上升时重新评估 | 规格负责人（yanheng） | 进开发前确认 scope |
| R2 | P1（已接受） | 全量业务数据明文沉淀 + 全局可见不脱敏 | 目标库含受监管 PII | 合规风险 | refine §行为规格7；需求方接受 | PRD 注明前提"内部/受控部署、目标库敏感度可接受"；若违反需回调结果范围/脱敏决策 | 规格负责人（yanheng） | 进开发前确认 scope |
| R3 | P2 | 列表分页缺失 | 历史累积（全量无上限放大） | `GET /api/conversations` 返回过慢 / OOM | 现读 Redis `KEYS *`，迁 PG 后若不分页同样退化 | PRD 必须纳入列表分页 + 排序（默认 `last_message_at` 倒序） | 后端实现 | PRD 阶段 |
| R4 | P2 | 单条超大结果（百万行）写入单条 JSONB | 单次返回巨量行查询 | 单行/单事务过大（PG TOAST 可承载但有代价） | refine §风险 P2；有意不截断 | 可选：单行大小监控/告警（不截断前提下） | 后端实现 | PRD/实现 |
| R5 | P2 | 双写一致性（异步 best-effort 缺条目） | PG 写失败 | 历史偶发缺条目 | refine §应失败边界 | 以 Redis 为热路径真相、PG 历史 best-effort；PRD 注明；如需强一致可补对账（可选） | 后端实现 | PRD 阶段 |
| R6 | P2 | 级联删除耦合 memory-profile 工作流 | 删会话级联 `conversation_summaries` | 可能影响 summary 派生的画像统计 | refine §行为规格8；`conversation_summaries` 属另一工作流 | 与 memory-profile 工作流对齐：确认级联不破坏画像统计；未来迁 `user_id` 同步改两处 | 后端实现 | PRD/实现 |
| R7 | P3 | 新表需 Alembic 迁移 | 引入 `chat_conversations`/`chat_messages` | — | 仓库已有 `alembic/`（`env.py` 用 `Base.metadata`）+ 多个 versions 迁移；`config/database.py` 不调 `create_all` | issues 阶段新增一个 Alembic migration，沿用现有模式 | 后端实现 | issues 阶段 |
| R8 | P3 | 实现模式一致性 | 新表用 ORM 还是 raw `text()` SQL | 维护摩擦 | 现有 app-DB 业务表（profiles/summaries）为 raw SQL | PRD/实现时全局统一（沿用 raw SQL 或统一 ORM） | 后端实现 | PRD 阶段 |
| R9 | P3 | `status` 快照标签 / confirm stub | `need_confirm` 永不转 success | 轻微认知偏差 | `gateway.py` confirm 端点为 stub | PRD 注明 status 为写入时快照、不做状态流转 | 规格负责人 | PRD 阶段 |
| R10 | P3 | 存量 Redis 会话不迁移 | 上线切换 | 上线前旧会话无法回看 | refine §风险 P3 | 接受；PRD 注明"历史从上线点开始累积" | — | — |

### 需要补充的问题（PRD 必须落实，非评审阻塞）

1. 列表分页/排序/筛选的具体规则（R3）。
2. "仅手动清理"的最小操作面：仅单条删除，还是含"批量按保留期清理"的管理端动作（R1）。
3. `_query_store` 内存 dict 是否改读 PG（`GET /api/query/{id}` 顺带清理）。

### Questions For User / Required Refinement

不适用（Status: ready）。如 R1/R2 的 scope 前提（内部/demo、目标库敏感度可接受）不成立，需回 `team-spec-refine` 重新决策保留策略与结果范围。

### 建议改写（PRD 前置检查清单）

PRD 必须显式包含以下条款，否则工程拆解会有缺口：

- **数据模型**：`chat_conversations` / `chat_messages` 两表 + 一个 Alembic 迁移；`status` 快照标签；无 `deleted_at`；ORM/raw-SQL 模式全局统一。
- **行为**：异步 fire-and-forget 双写（不阻塞热路径）；hard delete + 级联 `conversation_summaries`；全部尝试入库（含 error/need_confirm/empty/dry_run）。
- **回看 API**：`GET /api/conversations`、`GET /api/conversations/{sid}`、`DELETE /api/conversations/{sid}` 改读/写 PG + 列表分页。
- **运营**：明确"仅手动清理、无自动任务"为有意决策（R1），预留"自动保留期清理"为后续可选 issue；`/admin` 无门禁、默认 admin（见全局 CONTEXT）。
- **范围前提**：内部/受控部署、目标库敏感度可接受（R2）；超出则回调结果范围/脱敏。

---

## 历史评审（第 1 轮，2026-06-23）

- **评审对象**：`refine.md`（第 1 轮）
- **Status**：`needs refinement`（已被第 2 轮复查取代）

### 结论（第 1 轮）

不 ready 进入 PRD。核心行为已收敛，但存在 1 个 P0（无限增长的缓解机制欠定义）和若干影响 schema 与合规的关键 P1 未决议。最大风险来自**权限与合规维度**：全量业务结果数据将沉淀进应用库，而删除语义与历史可见性尚未确定。

### 阻塞项（第 1 轮）

| 等级 | 阻塞项 | 为什么阻塞 | 建议动作 | Owner | 截止点 |
|---|---|---|---|---|---|
| P0 | 保留兜底"机制"未定义（refine 已要求必须实现保留期/总量上限，但未定配置位置与清理触发方式） | 全量结果 + 无单条上限 = 无限增长；refine 自己标了"否则 P0"，但缓解措施只有目标没有机制，PRD 无法据此落地 | 回 refine 明确：配置位置（`.env` 或管理端 API）、默认值、清理执行方（后台定时任务 vs 管理员手动）、最旧优先算法 | 规格负责人（yanheng） | 进入 PRD 前 |
| P1 | 删除语义未定（hard delete vs soft delete；是否级联清理 `conversation_summaries` 等关联） | 影响 schema（是否要 `deleted_at`）、隐私合规（业务数据是否真删）、与 memory-profile 关联表的级联一致性 | 回 refine 做产品决策（见 Questions For User #1） | 规格负责人（yanheng） | 进入 PRD 前 |
| P1 | 历史可见性 + 全量业务数据沉淀的合规许可未定 | 系统无用户身份，`GET /api/conversations` 当前全局可见；全量结果会把目标库（可能含 PII）的业务数据复制进应用库。若不做判断，PRD 会默认"所有人可见所有查询与结果" | 回 refine 确认是否接受"全局可见 + 不脱敏"，或需隔离/脱敏（见 Questions For User #2） | 规格负责人（yanheng） | 进入 PRD 前 |

### Questions For User（第 1 轮，回到 team-spec-refine 确认）

1. **删除语义**：用户删除一条会话时，是 hard delete 还是 soft delete？是否需要同步清理该 session 在 `conversation_summaries` 里的摘要？
2. **历史可见性与脱敏**：是否接受"全局可见 + 不脱敏"，还是需要按 session_id/数据源做可见性隔离 / 对结果做脱敏？
3. **双写性能意图**：是否要求"PG 历史写入不得阻塞查询热路径"（异步 fire-and-forget，失败仅记日志）？
4. **保留兜底机制**：保留期/总量上限的配置放在 `.env` 还是管理端 API？默认值多少？清理由后台定时任务触发还是管理员手动？是否需要对"单条超大结果"加监控/告警（在不截断前提下）？

> 第 2 轮 refine 已全部回填上述 4 问，结论见本文件顶部"复查（第 2 轮）"。
