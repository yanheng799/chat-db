# 数据源连接与元数据提取 对齐材料

> 对应 PRD：`team-spec/active/2026-06-05-db-connection-metadata/prd/prd.md`
> 本材料服务于评审讨论，PRD 仍是工程拆解的权威输入。

## 1. 目标

让系统能连接管理员配置的业务数据库（PG 或 MySQL），自动提取表/字段/索引/外键结构信息，存入应用 PostgreSQL，并通过定时和手动同步保持元数据最新。这是后续语义匹配、SQL 生成和查询执行的前置条件。

## 2. 背景与现状

项目处于骨架阶段，16 个包全部为空。目前系统无法连接任何外部数据库，也没有目标数据库的结构信息。没有元数据，Phase 2（语义学习）、Phase 3（知识库构建）、Phase 5（单步查询）都无法进行。

本轮交付的是整个数据管线的第一层——数据源接入和元数据采集。

## 3. 本次做什么

- 数据源配置管理 API（CRUD + 连接测试 + 激活/停用），配置存应用数据库，密码加密存储
- 只读连接层，支持 PostgreSQL（asyncpg）和 MySQL（asyncmy）两种引擎
- 元数据提取（表/字段/索引/外键，含表类型 TABLE/VIEW），按数据源 ID 隔离
- 7 张新表，Alembic 管理 schema 迁移
- 定时全量同步 + 手动同步（全量或指定表），差异更新，变更日志
- 首次激活时异步提取，API 立即返回，通过 sync-logs 查进度

## 4. 本次不做什么

- 前端管理界面（Phase 10）
- 错误触发同步（Phase 7）
- 向量库/图谱更新（Phase 3）
- 元数据学习 L1/L2（Phase 2）
- API 鉴权（Phase 9）
- 行数提取、数据采样
- 运行时多数据源切换

## 5. 用户路径变化

本轮无前端 UI，管理员通过 API 操作。核心路径：

1. 管理员调用创建 API 添加数据源配置（引擎、连接信息、可选 schema 白名单）
2. 调用测试连接 API 验证可达性
3. 调用激活 API，系统后台开始提取元数据
4. 通过 sync-logs API 查看提取进度
5. 提取完成后通过 metadata API 查看概览
6. 后续 schema 变更时，手动触发同步（全量或指定表），或等待定时同步

系统定时任务每天自动扫描激活数据源的 schema 变更。

## 6. 关键设计决策

**决策 1：数据源配置存数据库，不入 .env**

配置通过 API 动态管理，存应用 PostgreSQL。.env 仅保留应用基础设施（应用 PG、Redis、Neo4j、加密密钥）。

选择原因：数据源配置是运行时管理数据，不属于部署参数。从 Phase 1 就用数据库存储，避免后续从 .env 迁移的转换成本。

取舍：Phase 1 需要额外建 data_sources 表和 API，但换来后续前端管理界面的直接对接。

影响：需要加密存储密码（Fernet），`.env` 新增 `ENCRYPTION_KEY` 配置项。

**决策 2：PG 和 MySQL 双引擎，Phase 1 就支持**

通过 SQLAlchemy dialect 抽象引擎差异。PG 用 asyncpg，MySQL 用 asyncmy。提取器各实现一份 information_schema 适配。

选择原因：企业环境 PG 和 MySQL 混用常见，只支持一种会排除部分用户。SQLAlchemy 已提供引擎抽象，额外成本可控。

取舍：提取逻辑需要两套适配（PG 注释走 pg_catalog，MySQL 走 information_schema），测试量翻倍。

影响：新增 asyncmy 依赖（社区较小，需验证 MySQL 5.7+/8.0+ 兼容性）。

**决策 3：首次提取异步执行，手动同步支持指定表**

激活数据源时 API 立即返回，后台异步提取。手动同步可选 table_scope 参数只检查指定表。

选择原因：目标库可能数千张表，同步提取会阻塞 API 数分钟。表级同步让管理员在 schema 变更后快速更新单张表。

影响：需要并发防护（同一数据源同一时刻仅允许一个 running sync_log）。

## 7. 研发需要关注什么

**数据模型**

7 张新表，全部使用 Alembic 管理。FK 约束需设 ON DELETE CASCADE（删除数据源时级联删除元数据）。metadata_tables 需要唯一约束 (data_source_id, schema_name, table_name)，其余表类似。metadata_tables 新增 table_type 字段（BASE TABLE / VIEW / MATERIALIZED VIEW），Phase 5 SQL 生成时需要区分。

**依赖变更**

pyproject.toml 新增 4 个包：asyncmy、cryptography、alembic、apscheduler。.env.example 新增 ENCRYPTION_KEY（必须配置）和 METADATA_SYNC_INTERVAL_HOURS（默认 24）。

**PG vs MySQL 适配**

PG 的表/字段注释不在标准 information_schema 中，需额外查询 pg_catalog.pg_description。索引查询也走 pg_catalog。MySQL 全部走 information_schema。两套提取逻辑需要分别测试。

**并发与状态**

同一 data_source 同一时刻仅允许一个 running sync_log，冲突返回 HTTP 409。sync_log 有三种状态：running / success / failed。首次提取、定时同步、手动同步共用同一套 diff 逻辑。

**安全**

密码加密用 Fernet（cryptography 包），密钥从 .env 读取。API 响应永不返回密码。目标数据源连接强制只读 + 超时保护。Phase 1 无 API 鉴权（Phase 9 补齐）。

**测试入口**

需要 mock information_schema 查询结果测试提取逻辑。手工验收需要真实的 PG 和 MySQL 数据库。pytest-asyncio 已配置 asyncio_mode=auto。

## 8. 风险与待决问题

**Risk** — asyncmy 兼容性

asyncmy 社区较小，对 MySQL 5.7 / 8.0 / MariaDB 的兼容性需要实现阶段验证。如果遇到兼容问题，可回退到 aiomysql。影响：MySQL 数据源不可用。

建议决策人：研发负责人。

**Risk** — 大数据量提取性能

目标库有数千张表时，全量提取可能耗时较长。当前无提取超时配置。

缓解：sync_log 记录 started_at / finished_at 可监控耗时，后续可加超时和增量提取。

**Risk** — 加密密钥丢失

ENCRYPTION_KEY 丢失意味着所有数据源密码不可恢复。

缓解：部署文档强调密钥备份，后续可加密钥轮换机制。

**Discussion** — Phase 1 API 无鉴权

数据源管理 API 涉及敏感操作（密码存储、数据库连接），Phase 1 无用户系统暂不鉴权。是否需要在 Phase 1 就做基础鉴权（如 API Key）？

建议决策人：产品负责人 + 安全。

**Discussion** — 删除保护

删除激活数据源会级联删除所有元数据。是否需要在删除前强制二次确认参数（如传入 `confirm=true`）？Phase 1 无前端 UI，API 层级联删除是否可接受？

建议决策人：产品负责人。

## 9. 对齐结论

本轮评审需确认四个判断：

1. **是否值得做**：元数据采集是整个数据管线的前置条件，无替代方案。
2. **范围是否一致**：Phase 1 只做配置管理 + 连接层 + 提取 + 同步 + 日志。前端 UI、鉴权、学习、向量/图谱更新全部排除。
3. **风险是否可接受**：主要风险是 asyncmy 兼容性和密钥管理，均可实现阶段缓解。API 无鉴权需要产品确认是否接受。
4. **是否 ready for engineering**：PRD 验收标准 15 条 Given-When-Then 覆盖主要场景，可进入工程拆解。

评审通过后建议进入 `team-prd-to-issues` 拆解工程任务。
