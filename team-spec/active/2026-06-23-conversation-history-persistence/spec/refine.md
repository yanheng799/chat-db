# 历史会话持久化 — 规格细化

- **slug**：`2026-06-23-conversation-history-persistence`
- **状态**：refining 完成（第 2 轮，`team-spec-review` 反馈已回填，待复查）
- **基线**：现有 `src/memory/session.py`（Redis 会话）+ `src/api/gateway.py`（会话/对话 API）；应用数据库（PostgreSQL）
- **依赖**：Redis（热上下文层，已存在）、应用 PostgreSQL（冷历史层，已存在）、`data_sources` 表（每条消息关联数据源）、`conversation_summaries`（memory-profile 工作流，已实现，删除时级联）

## 需求复述

把当前仅存在于 Redis（30min TTL + 仅最近 10 轮 + 每轮截断 500 字）的对话历史，**持久化进应用 PostgreSQL**，使用户在 TTL 过期、浏览器关闭、服务重启之后，仍能回看「我问过什么、生成过什么 SQL、得到过什么结果」。Redis 继续承担实时热上下文（喂给 LLM 的最近若干轮），PG 只做冷历史持久化与回看读取；PG 写入异步进行、不阻塞查询热路径。

## 术语（本规格局部）

| 术语 | 定义 |
|------|------|
| 历史会话（conversation） | 一次连续对话的容器，对应现有 Redis 的一个 `session:{sid}`。一个会话含多条消息。 |
| 消息/轮次（message / turn） | 一次"用户提问 → 系统应答"的捆绑记录，对应现有 `add_turn(user, assistant, sql)` 的一个 turn。 |
| 热上下文层 | Redis。低延迟、有界（最近 10 轮 / 30min TTL），供 LLM 多轮上下文使用。本规格不改变其行为。 |
| 冷历史层 | 应用 PostgreSQL。全量、持久、用于回看。 |
| 双写 | 在现有 `gateway.py` 的 `add_turn` 调用点，除写 Redis 外，**异步**追加写一条 PG 历史消息。 |

## 范围内（本规格）

- **持久化**：每个会话 + 每条消息（含全量结果数据）写入应用 PG。
- **回看 API**：列表（现有 `GET /api/conversations`）+ 详情（现有 `GET /api/conversations/{sid}`）改为读 PG，使其在 Redis TTL 过期/重启后仍可返回。
- **删除**：用户/管理员可手动删除整条会话（现有 `DELETE /api/conversations/{sid}`），**hard delete**，连同其全部消息与该 session 的 `conversation_summaries` 摘要级联物理删除。
- **分层架构**：Redis 热上下文层保持现状不动；PG 仅作冷历史层；双写在 `add_turn` 处**异步 fire-and-forget** 追加。
- **全量写入**：所有查询尝试（成功 / 出错 / 需确认 / 空结果 / dry-run）都写入，每条带 `status` 快照标签。

## 范围外 / 延期

- 真实用户身份 / 登录 / 多租户隔离。**当前系统无认证、默认所有访问者为 admin**（`/admin` 无门禁；详见全局 `team-spec/CONTEXT.md`），故历史全局可见、不做用户/角色隔离。
- 自动保留期/总量清理任务（本期仅手动清理，见行为规格 4 与风险 P1-残留）。
- 跨设备 / 跨会话恢复（依赖用户身份，延期）。
- 审计级不可篡改留痕（动机是回看，不是合规审计；消息写入后不可变是默认行为，但无独立审计链）。
- 用历史做长程上下文检索 / RAG（分层后 LLM 上下文仍只走 Redis 最近若干轮）。
- 历史语义搜索（本期列表先按时间排序；关键词/语义搜索留后续）。

## 行为规格（已定）

1. **动机**：用户回看历史对话（持久化 + 列表 + 详情浏览）。
2. **结果数据范围**：完整结果数据（全量 `rows` / `columns`），目的是回看时能重新展示 / 导出当时的确切结果。
3. **单条兜底**：**不设上限，一律全量存**（即使返回数万行也原样写入）。写入路径不截断。
4. **保留策略**：默认永久保留；清理**仅靠管理员/用户手动删除**（整条会话级，hard delete），**不实现自动保留期/总量清理任务**。这是对"无限增长"风险的**明确接受**（见风险 P1-残留），适合小规模内部/demo；若部署规模扩大需补自动清理。
5. **架构**：分层 —— Redis 仍是热上下文层（现有 SSE 流程与 10 轮 / 30min 行为不变），PG 只做冷历史持久化；双写在 `add_turn` 处追加，**异步 fire-and-forget，不得阻塞查询热路径，PG 写失败仅记日志、不回滚 Redis**。回看读 PG，实时上下文读 Redis。
6. **写入范围**：全部尝试都写（成功 / 出错 / 需确认 / 空结果 / dry-run），每条带 `status` **快照标签**（不做状态流转）。
7. **可见性与脱敏**：全局可见、不脱敏。所有访问者（默认 admin）可见全部历史与全量结果；全量业务数据明文沉淀进应用库，**合规风险已接受**（前提：内部/受控部署、目标库数据敏感度可接受）。
8. **删除语义**：hard delete。删除整条会话时，物理删除其全部消息与全量结果，并**级联清理同 `session_id` 的 `conversation_summaries`** 摘要（避免孤儿）。不可恢复。

## 数据模型（待实现确认，初稿）

两层实体，沿用现有 session→turns 形状。**仅作规格层约定，非代码改动**：

- **`chat_conversations`**（建议加 `chat_` 前缀，以区别已实现的 `conversation_summaries`）：`id`(PK = session_id UUID)、`title`（沿用首条提问前 50 字自动生成）、`created_at`、`updated_at` / `last_message_at`、`message_count`。
- **`chat_messages`**（每轮一条）：`id`(PK)、`conversation_id`(FK)、`seq`(轮次序号)、`user_text`、`assistant_summary`、`sql`、`result`(JSONB：`{columns, rows, execution_time_ms}`，无结果时 null)、`status`(`success`/`error`/`need_confirm`/`empty`/`dry_run`)、`error`(文本，可 null)、`data_source_id`、`created_at`。
  - **无 `deleted_at`**（hard delete，不做软删）。
  - `status` 为写入时**快照标签**，不做状态流转（现有 `POST /query/{id}/confirm` 为 stub，`need_confirm` 不会自动转 `success`）。
  - 建议沿用现有 app-DB 业务表的 raw `text()` SQL 模式（与 `profiles`/`summaries` 一致），或统一为 ORM（PRD/实现时决定，需全局一致）。

实现注意（只读观察，非本技能改动）：现有 `add_turn(sid, user_text, assistant_text, sql)` 调用点（`gateway.py` finally 块）目前只传 `summary` 与 `sql`，**未携带完整 `result` 字典**；持久化全量结果需要在该处把 `result["result"]`（含 rows/columns）一并传入持久化调用。`result` 变量在该作用域内可见。

## 验收口径

**应通过**：
- 用户发起一次查询并拿到结果 → 关闭浏览器、等 Redis 30min TTL 过期、重启服务后 → 仍能在历史列表看到该会话，点进详情能看到提问、SQL 与**完整结果**（行列一致）。
- 一次报错的查询 → 出现在历史中，`status=error`，可看到错误信息。
- 一次 `need_confirm` 的查询 → 出现在历史中，`status=need_confirm`，SQL 可见。
- 一次返回大量行的查询 → 全量写入（按决策不截断）。
- 用户/admin 删除一条会话 → 该会话的全部消息、全量结果，以及该 `session_id` 的 `conversation_summaries` 一并物理消失（hard delete + 级联）。
- 多轮追问 → LLM 上下文仍来自 Redis 最近若干轮（分层后实时上下文行为不变）。
- PG 写入耗时/失败 → 不影响实时查询响应（异步 fire-and-forget）。

**应失败 / 边界**：
- Redis 不可用 → 实时上下文降级（沿用现有行为），但 **PG 历史不受影响**、回看仍可用。
- PG 写入失败 → 记日志、**不阻断主查询流程**，该条历史可能缺失（best-effort）。

## 轻量风险扫尾

- **P1（残留，已接受）**：全量结果 + 无单条上限 + **仅手动清理、无自动兜底** → 应用库增长**仅靠人工删除**控制。已由需求方明确接受（内部/demo 规模）；若部署规模扩大或数据敏感度升高，必须补自动保留期/总量清理任务。**这是本规格最大的残留风险。**
- **P1（已接受）**：**隐私 / 合规** —— 全量业务数据明文沉淀进应用库、全局可见不脱敏。已接受（前提：内部/受控部署）。若目标库含受监管 PII，需回调"结果范围/脱敏"决策。
- **P2**：**单行体积** —— "不设上限 + 全量存"下，单次返回百万行的查询会写入单条超大 JSONB（PG TOAST 可承载但有上限与性能代价）。建议作为可选运维项加"单行大小监控/告警"（用户未选自动方案，监控是否实现待定）。
- **P2**：**双写一致性** —— 异步 fire-and-forget 下，PG 写失败会导致历史缺条目（best-effort）。以 Redis 为热路径真相、PG 历史 best-effort；如需强一致可补对账/补写（可选）。
- **P2**：**与 `conversation_summaries` 命名/键邻接** —— 两者都以 `session_id` 关联。已用 `chat_` 前缀区分；删除会话时级联清理摘要，避免孤儿。未来迁 `user_id`（Phase 9）需同步改两处。
- **P3**：上线时 Redis 中的存量会话**不迁移**到 PG（历史从上线点开始累积）。
- **P3**：现有 app-DB 业务表用 raw `text()` SQL 而非 ORM；新表实现模式需全局一致（见数据模型备注）。

## 开放问题（剩余，均可留 PRD/实现）

1. **列表交互形态**：排序（默认按 `last_message_at` 倒序）/ 分页 / 筛选 / 关键词搜索的具体规则 —— 留 PRD。
2. **标题可编辑性**：是否允许用户改会话标题（当前仅自动生成）。
3. **`_query_store` 内存 dict 去向**：`GET /api/query/{query_id}` 现读进程内存 dict（重启即丢），是否改读 PG 历史作为顺带清理项。
4. **批量手动清理动作**：除单条删除外，是否提供"按保留期手动批量清理"的管理端动作（vs 仅单条删除）—— UI 细节，留 PRD。
5. **超大结果监控**：是否实现"单行体积监控/告警"作为可选运维项（见风险 P2）。

## Change Log

- 2026-06-23（第 1 轮）：确认 6 项核心行为 —— 动机=回看；结果范围=全量；单条兜底=不设上限；保留=永久+手动删+管理端兜底；架构=分层(Redis 热+PG 冷 双写)；写入范围=全部尝试+status 标记。补全数据模型初稿、验收口径、风险扫尾与开放问题。
- 2026-06-23（第 2 轮）：回填 `team-spec-review` 的 4 个 Questions For User —— ① 可见性=全局可见+不脱敏(接受)；② 删除=hard delete+级联 `conversation_summaries`；③ 双写=异步 fire-and-forget 不阻塞热路径；④ 保留兜底=仅手动清理(无自动任务，**接受增长靠人工控制的残留 P1 风险**)。同时把"当前默认 admin/无门禁"作为跨需求事实记入全局 `team-spec/CONTEXT.md`。补全数据模型备注（`chat_` 前缀、无 `deleted_at`、status 快照、raw SQL 模式）、验收口径（删除级联）、风险重排（P0 降级为已接受残留 P1）。
