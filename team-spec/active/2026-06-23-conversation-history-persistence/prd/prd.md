# 历史会话持久化

- **slug**：`2026-06-23-conversation-history-persistence`
- **基线规格**：`team-spec/active/2026-06-23-conversation-history-persistence/spec/refine.md`（第 2 轮）
- **评审状态**：`Status: ready`（见 `spec/reviews.md` 第 2 轮复查）
- **版本/日期**：v1 / 2026-06-23

## 问题陈述

当前对话历史完全存在 Redis：30 分钟无活动即 TTL 过期、只保留最近 10 轮、每轮截断 500 字，进程重启后内存中的查询明细也会丢失。结果是用户**无法跨会话回看**"我问过什么、生成过什么 SQL、得到过什么结果"——关掉浏览器或隔天再来，对话就没了。本需求把对话历史持久化进应用 PostgreSQL，使其在 TTL 过期、浏览器关闭、服务重启之后仍可回看。

## 目标

- 用户在 Redis TTL 过期、浏览器关闭、服务重启后，仍能回看历史会话的提问、SQL 与**完整结果**。
- 回看 API（列表 / 详情）改读应用 PG，不再依赖 Redis 易失性。
- 历史写入**不降低实时查询延迟**（异步，不阻塞热路径）。

## 非目标

- 用户身份 / 登录 / 多租户隔离（当前无认证、默认所有访问者为 admin）。
- 自动保留期 / 总量清理任务（本期仅手动删除）。
- 跨设备 / 跨会话恢复（依赖用户身份）。
- 审计级不可篡改留痕（动机是回看，不是合规审计）。
- 用历史做长程上下文检索 / RAG（LLM 上下文仍只走 Redis 最近若干轮）。
- 历史关键词 / 语义搜索（本期列表按时间排序）。

## 用户与场景

1. 作为查询用户（默认 admin），我希望在 Chat UI 看到历史会话列表，以便找回之前的对话。
2. 作为查询用户，我希望点开历史会话看到当时的提问、SQL 和完整结果，以便复用或导出。
3. 作为查询用户，我希望删除某条不再需要的历史会话（及其全部消息），以保持列表整洁。
4. 作为查询用户，我希望即使服务重启，昨天的对话仍能打开。
5. （失败场景）作为查询用户，当某次查询出错时，我希望在历史里看到这条失败记录和错误信息，以便复盘。

## 当前状态

- **Redis 会话层**（`src/memory/session.py`）：`create_session` / `add_turn` / `get_context` / `list_sessions` / `end_session` + `ResultCache`。30min TTL、最近 10 轮、每轮 500 字截断；`list_sessions` 用 `KEYS session:*`（生产级隐患）。
- **API 网关**（`src/api/gateway.py`）：`POST /api/query`（SSE 流式，`add_turn` 在 `finally` 块对全部结果调用）、`POST /api/session`、`GET /api/conversations`、`GET /api/conversations/{sid}`、`DELETE /api/conversations/{sid}`、`GET /api/query/{id}`（读进程内存 `_query_store` dict，重启即丢）、`confirm`/`cancel`（stub）。
- **应用 PG**：SQLAlchemy 2.0 async + **Alembic** 迁移（`alembic/versions/`）；已有 `metadata_*`、`data_sources`、`user_profiles`、`conversation_summaries` 等表。
- **缺口**：无持久化的会话/消息表；历史完全易失；列表依赖 Redis `KEYS`；`_query_store` 为进程内存。

## 方案描述

**分层架构**：Redis 继续承担实时热上下文层（喂给 LLM 的最近若干轮，行为不变）；新增应用 PG 作为冷历史层。每次查询在现有 `add_turn` 调用点**异步**双写一条 PG 消息（含全量结果）。回看 API（列表 / 详情）改读 PG；删除改写 PG（hard delete，并级联清理该 session 的 `conversation_summaries`）。所有查询尝试（成功 / 出错 / 需确认 / 空结果 / dry-run）都写入，每条带 `status` 快照标签。

**主路径**：用户提问 → SSE 流式返回结果 → 异步写一条 PG 消息（提问/SQL/全量结果/status）→ 次日用户打开历史列表（读 PG，分页）→ 点开看到完整对话与结果。

## 范围

### 范围内

- PG 持久化会话 + 消息（含全量结果数据）。
- 回看 API（`GET /api/conversations`、`GET /api/conversations/{sid}`）改读 PG + 列表分页。
- 整条会话删除（`DELETE /api/conversations/{sid}`）改写 PG，hard delete + 级联 `conversation_summaries`。
- 在 `add_turn` 处异步 fire-and-forget 双写。
- 全部查询尝试入库 + `status` 快照。

### 范围外

- 用户身份 / 角色隔离、自动清理任务、跨设备恢复、审计留痕、历史 RAG、语义搜索、会话标题编辑（见开放问题）。

## 功能需求

1. 系统必须把每次查询尝试（成功 / 出错 / 需确认 / 空结果 / dry-run）作为一条消息持久化到应用 PG，并带 `status` 快照标签。
2. 系统必须在每条消息中保存完整结果数据（`columns` / `rows` / `execution_time_ms`），写入路径不截断。
3. 系统必须**异步**执行 PG 历史写入，不阻塞查询热路径；写入失败仅记日志、不回滚 Redis、不影响实时查询。
4. 用户必须能查看历史会话列表（读 PG，分页，默认按 `last_message_at` 倒序）。
5. 用户必须能查看某会话的全部消息（含提问 / SQL / 完整结果 / status）。
6. 用户必须能删除整条会话（hard delete），系统须级联清理该 `session_id` 的 `conversation_summaries`。
7. 列表与详情在 Redis TTL 过期或服务重启后仍可返回。

## 业务规则

- 历史 `message` 写入后**不可变**（append-only）；`status` 为写入时**快照标签**，不做状态流转。
- 默认**永久保留**；清理仅靠手动删除整条会话；**不实现自动保留期 / 总量清理任务**（有意决策，见已接受风险 R1）。
- 可见性：**全局可见、不脱敏**（前提：内部 / 受控部署、默认 admin）。
- 一个会话可跨多个 `data_source`；每条消息记录其 `data_source_id`。
- 会话标题沿用现有逻辑（首条提问前 50 字自动生成）。

## 边界情况与错误状态

- **PG 写入失败**：记日志，不阻断查询；该条历史可能缺失（best-effort）。
- **Redis 不可用**：实时上下文降级（沿用现有行为），PG 历史与回看不受影响。
- **超大结果集（百万行）**：全量写入单条 JSONB（不截断，有意决策）；建议加单行大小监控（见开放问题 5）。
- **`need_confirm` 轮次**：写入 `status=need_confirm`；现有 `confirm` 端点为 stub，不会转为 `success`。
- **删除不存在的会话**：幂等返回成功（或 404，实现时定）。
- **历史列表为空**：返回空列表。

## 数据与状态

- **`chat_conversations`**：`id`(PK = `session_id` UUID)、`title`、`created_at`、`updated_at` / `last_message_at`、`message_count`。**无 `deleted_at`**（hard delete）。`chat_` 前缀以区别已实现的 `conversation_summaries`。
- **`chat_messages`**：`id`(PK)、`conversation_id`(FK)、`seq`、`user_text`、`assistant_summary`、`sql`、`result`(JSONB `{columns, rows, execution_time_ms}`，无结果时 null)、`status`(`success`/`error`/`need_confirm`/`empty`/`dry_run`)、`error`(text, 可 null)、`data_source_id`、`created_at`。
- **生命周期**：消息只追加；会话随首条消息创建、随删除物理消失并级联清理摘要。
- **schema 引导**：通过 **Alembic 迁移**创建新表（沿用 `alembic/versions/` 现有模式）。
- **实现模式**：与现有 app-DB 业务表一致（raw `text()` SQL），或全局统一为 ORM（见开放问题 6）。

## 权限与合规

- **可见性 / 操作权限**：所有访问者（默认 admin）可读全部历史与全量结果、可删除任意会话。无用户 / 角色隔离（`/admin` 无门禁，见全局 `team-spec/CONTEXT.md`）。
- **隐私**：全量业务结果**明文沉淀**进应用库、不脱敏。**前提假设**：内部 / 受控部署、目标库敏感度可接受；若目标库含受监管 PII，需回调结果范围 / 脱敏决策（见已接受风险 R2）。
- **审计**：无独立审计链。

## 发布与运营

- **迁移**：新增 Alembic 迁移建 `chat_conversations` / `chat_messages`，上线时执行。
- **存量数据**：Redis 中既有会话**不迁移**，历史从上线点开始累积。
- **功能开关**：非必需（分层不动热路径，低风险）；如需可加 env 开关控制是否启用 PG 持久化，便于灰度 / 回滚。
- **监控**：建议 PG 写入失败计数、单行大小告警（可选，见开放问题 5）。
- **运营清理**：仅手动删除；无自动任务。预留"自动保留期清理"为后续可选 issue。
- **回滚**：关闭 PG 双写即回退到纯 Redis 行为（回看随之失效），实时查询不受影响。

## 实现决策

- **架构**：分层（Redis 热 + PG 冷）；双写点在 `gateway.py` 的 `add_turn` 调用处，**异步 fire-and-forget**。
- 双写需把完整 `result`（`columns`/`rows`）传入持久化调用——现有 `add_turn(sid, user_text, assistant_text, sql)` 只传 `summary`/`sql`，而 `result` 变量在 `_run_pipeline` 作用域内可见。
- **回看 API 改动**：`GET /api/conversations`（list，读 PG + 分页）、`GET /api/conversations/{sid}`（detail，读 PG）、`DELETE /api/conversations/{sid}`（写 PG + 级联 `conversation_summaries`）。API 契约对外不变，前端列表 / 详情组件基本无需改动。
- **不改动** SSE 查询主流程与 Redis 热上下文行为（`get_context` 仍读 Redis 最近若干轮）。
- **受影响模块**：`src/memory/`（新增持久化）、`src/api/gateway.py`（回看 API 改读 PG、双写钩子）、新增 Alembic 迁移。
- **`_query_store`**（`GET /api/query/{id}` 的内存 dict）：建议顺带改读 PG（见开放问题 3）。

## 测试决策

- **外部行为测试**（不测实现细节）：
  - 查询后重启服务 + Redis TTL 过期 → 历史列表与详情仍含该次提问 / SQL / 完整结果。
  - 出错查询 → 历史含 `status=error` + 错误信息。
  - `need_confirm` 查询 → 历史含 `status=need_confirm` + SQL。
  - 删除会话 → 消息与该 session 的 `conversation_summaries` 一并消失。
  - 模拟 PG 写失败 → 查询仍正常返回、延迟不显著上升、仅日志。
  - 超大结果 → 全量写入（行数一致）。
- **自动化重点**：持久化层（写 / 读 / 删除 / 级联）、回看 API（分页、TTL 过期后可读）、异步不阻塞（查询延迟不因 PG 写入上升）。
- **现有测试模式**：参考 `test/` 下 `test_config` / `test_metadata` 等模块结构。
- **手工验收**：跨天回看、删除、重启后回看。

## 验收标准

- **Given** 用户完成一次成功查询，**When** 服务重启且 Redis 30min TTL 过期，**Then** `GET /api/conversations` 仍列出该会话，`GET /api/conversations/{sid}` 返回提问 / SQL / 完整结果（行列一致）。
- **Given** 一次报错查询，**When** 查看历史，**Then** 该消息 `status=error` 且含错误信息。
- **Given** 一次 `need_confirm` 查询，**When** 查看历史，**Then** 该消息 `status=need_confirm` 且含 SQL。
- **Given** 用户删除会话 X，**When** 查询 X 的消息与 `conversation_summaries`，**Then** 均不存在（hard delete + 级联）。
- **Given** PG 写入失败，**When** 用户查询，**Then** 实时结果正常返回、延迟不显著上升、仅日志记录。
- **Given** 一次返回 N 行的查询，**When** 查看历史结果，**Then** `rows` 行数 = N（全量不截断）。
- **Given** 多轮追问，**When** LLM 构建上下文，**Then** 仍取 Redis 最近若干轮（行为不变）。

## 开放问题

1. **列表分页 / 排序 / 筛选具体规则**（页大小、offset vs 游标、是否按数据源筛选）——负责人：后端 / 产品；不解决影响：列表性能与 UX（R3）。
2. **"仅手动清理"的最小操作面**：仅单条删除 vs 含"批量按保留期清理"的管理端动作——负责人：产品；影响：R1 运营可控性。
3. **`_query_store` 是否改读 PG**（`GET /api/query/{id}`）——负责人：后端；影响：重启后 query 详情可用性。
4. **会话标题是否可编辑**——负责人：产品；影响：UX（低）。
5. **是否实现单行大小监控 / 告警**——负责人：后端 / 运维；影响：R4 可观测性。
6. **实现模式统一**（raw SQL vs ORM）——负责人：后端；影响：维护一致性。

## 补充说明

- **假设**：内部 / 受控部署；目标库敏感度可接受不脱敏；小规模使用可接受仅手动清理。
- **依赖**：Redis（热上下文，已存在）、应用 PG（冷历史，已存在）、Alembic（迁移，已存在）、`conversation_summaries`（memory-profile 工作流，删除时级联）。
- **关联规格**：`team-spec/active/2026-06-19-context-memory-profile`（`conversation_summaries` 来源；未来 Phase 9 迁 `user_id` 时两处需同步）。
- **已接受风险**：R1（仅手动清理 → 增长靠人工控制）、R2（全量不脱敏沉淀）——详见 `spec/reviews.md` 第 2 轮。两者均为 scope-conditional：若部署规模 / 数据敏感度前提变化，需回调保留策略与结果范围决策。
