# 数据源连接与元数据提取

## 问题陈述

Chat-DB 系统需要查询用户的业务数据库，但目前系统无法连接任何外部数据库，也没有目标数据库的结构信息。管理员无法配置要查询的数据源，系统无法获取表/字段/索引/外键等元数据，后续的语义匹配、SQL 生成和查询执行都无法进行。

需要一个基础能力：管理员通过 API 配置目标数据源（PostgreSQL 或 MySQL），系统建立只读连接、提取元数据、存入应用数据库，并通过定时和手动同步保持元数据最新。

## 目标

- 管理员可通过 API 完成数据源的增删改查、连接测试、激活/停用
- 系统可从目标数据源（PG 或 MySQL）提取完整的表/字段/索引/外键元数据
- 元数据按数据源 ID 隔离存储在应用 PostgreSQL 中，支持定时和手动同步
- 首次激活数据源后，管理员可在 10 分钟内（取决于表数量）看到完整的元数据概览

## 非目标

- 前端管理界面 UI（Phase 10 补齐，本轮只做后端 API）
- 错误触发同步（Phase 7）
- 向量库和图谱更新（Phase 3）
- 元数据学习 L1/L2（Phase 2）
- 运行时多数据源切换（V1 之后）
- 行数提取、数据采样
- API 鉴权（Phase 9 用户系统建立后统一处理）
- 数据采样（Phase 2 LLM 学习需要）

## 用户与场景

1. 作为**管理员**，我希望通过 API 添加一个 PostgreSQL 或 MySQL 数据源配置，以便系统能连接到我要查询的业务数据库。
2. 作为**管理员**，我希望在保存配置前测试数据源连接是否可达，以便避免无效配置入库。
3. 作为**管理员**，我希望激活一个数据源后系统自动提取元数据，以便我能查看数据库结构。
4. 作为**管理员**，我希望查看已提取的元数据概览（表数量、字段数量等），以便确认提取结果。
5. 作为**管理员**，我希望手动触发同步（全量或指定表），以便在 schema 变更后立即更新元数据。
6. 作为**管理员**，我希望查看同步日志和变更记录，以便了解元数据的变更历史。
7. 作为**系统定时任务**，我希望按配置的间隔自动扫描激活数据源的 schema 变更，以便保持元数据最新。

## 当前状态

项目处于骨架阶段（Phase 0 已完成），`src/db/`、`src/metadata/`、`src/config/`、`src/api/` 四个包仅有空的 `__init__.py`，无任何实现代码。

已有基础设施：
- `pyproject.toml` 定义了 16 个包的构建配置
- `.env.example` 包含应用 PG、Redis、Milvus、Neo4j、DashScope API 等配置
- `pytest` + `pytest-asyncio` + `ruff` 已配置就绪
- 应用 PostgreSQL 用于存储系统数据（用户画像、审计日志等）

缺口：
- `pyproject.toml` 缺少 MySQL 异步驱动（`asyncmy`）、加密库（`cryptography`）、迁移工具（`alembic`）和调度器（`apscheduler`）
- `.env.example` 缺少加密密钥（`ENCRYPTION_KEY`）和同步间隔（`METADATA_SYNC_INTERVAL_HOURS`）配置项

## 方案描述

管理员通过 REST API 管理数据源配置。数据源连接信息（含加密密码）存储在应用 PostgreSQL 的 `data_sources` 表中。系统支持同时存储多条配置，但同一时刻仅一条为激活状态。

激活数据源时，系统从数据库读取连接配置，创建 SQLAlchemy async 引擎（PG 用 asyncpg，MySQL 用 asyncmy），建立只读连接。如果该数据源尚无元数据，后台异步触发首次全量提取——从目标数据源的 `information_schema` 读取表/字段/索引/外键信息，存入应用的元数据表。

定时同步（APScheduler）和手动同步均使用相同的差异更新逻辑：对比目标数据源当前 schema 与已存元数据，检测变更（表增/删、字段增/删/改、索引增/删、外键增/删），写入变更日志后更新元数据表。手动同步还支持指定表范围，仅检查选中的表。

## 范围

### 范围内

- 数据源配置 CRUD + 连接测试 + 激活/停用
- 只读数据库连接层（PG + MySQL，SQLAlchemy async）
- 元数据提取（表/字段/索引/外键，含表类型 TABLE/VIEW/MATERIALIZED VIEW）
- 元数据存储（7 张表，Alembic 迁移管理）
- 定时全量同步 + 手动同步（全量或指定表）
- 同步日志和变更日志
- 密码加密存储（Fernet）

### 范围外

- 见"非目标"章节

## 功能需求

### 数据源配置管理

1. 系统必须提供 `POST /api/datasources` 创建数据源配置，接受引擎类型（postgresql/mysql）、连接参数和可选的 schema 白名单。
2. 系统必须对 `password_encrypted` 字段使用 Fernet 对称加密存储，加密密钥来自 `.env` 的 `ENCRYPTION_KEY`。
3. 系统必须在 API 响应中永不返回密码明文。
4. 系统必须提供 `GET /api/datasources` 列出所有配置（不含密码）。
5. 系统必须提供 `GET /api/datasources/{id}` 获取单个配置（不含密码）。
6. 系统必须提供 `PUT /api/datasources/{id}` 更新配置。
7. 系统必须提供 `DELETE /api/datasources/{id}` 删除配置，同时级联删除所有关联元数据。
8. 系统必须保证 `data_sources.name` 全局唯一。

### 连接测试

9. 系统必须提供 `POST /api/datasources/{id}/test` 测试数据源连接，返回成功/失败及错误信息。
10. 测试连接不保存任何状态，仅验证可达性和凭证有效性。

### 激活/停用

11. 系统必须提供 `POST /api/datasources/{id}/activate` 激活数据源。
12. 系统必须保证同一时刻全局仅一条配置为 `is_active = true`。激活新数据源时自动停用原激活数据源。
13. 激活时如果该数据源尚无元数据，系统必须异步触发首次全量提取，API 立即返回。
14. 停用数据源时，系统必须 dispose 对应的 SQLAlchemy 引擎。
15. 系统必须以 `data_source_id` 为 key 缓存 SQLAlchemy async 引擎实例，避免重复创建。
16. 应用关闭时，系统必须 dispose 所有缓存的引擎。

### 只读连接层

17. 系统必须通过 SQLAlchemy async 引擎连接目标数据源，PG 使用 asyncpg 驱动，MySQL 使用 asyncmy 驱动。
18. 每次连接必须强制只读：PG 执行 `SET TRANSACTION READ ONLY`，MySQL 执行 `SET SESSION TRANSACTION READ ONLY`。
19. 每次查询必须设置超时：PG 使用 `statement_timeout`，MySQL 使用 `max_execution_time`。

### 元数据提取

20. 系统必须从目标数据源的 `information_schema` 提取以下信息：
    - 表：schema_name、table_name、table_type（BASE TABLE / VIEW / MATERIALIZED VIEW）、table_comment
    - 字段：column_name、data_type、is_nullable、default_value、column_comment、is_primary_key、ordinal_position
    - 索引：index_name、column_names（列表）、is_unique
    - 外键：constraint_name、column_name、target_schema、target_table、target_column（仅显式声明的外键）
21. 系统必须不提取行数。
22. 提取范围：
    - 如果 `schema_whitelist` 不为 null，只提取指定 schema（PG）或 database（MySQL）列表中的表
    - 如果 `schema_whitelist` 为 null，提取所有非系统 schema/database 中的表
    - PG 默认排除：`pg_catalog`、`information_schema`、`pg_toast`、所有 `pg_temp_*`
    - MySQL 默认排除：`mysql`、`information_schema`、`performance_schema`、`sys`
23. 所有元数据记录必须关联 `data_source_id`。

### 同步

24. 系统必须使用 APScheduler 定时扫描激活数据源，间隔通过 `.env` 的 `METADATA_SYNC_INTERVAL_HOURS` 配置（默认 24 小时）。
25. 系统必须提供 `POST /api/datasources/{id}/sync` 手动触发同步。
26. 手动同步支持可选的 `table_scope` body 参数：`[{"schema": "public", "table": "orders"}]`。不传则全量同步，传了则仅检查指定表。
27. 表级同步的检查范围：指定表的字段（增/删/改）、索引（增/删）、外键（增/删）。
28. 表级同步时，如果指定表在目标库中已不存在，系统必须记录 `table_removed`；如果指定表在目标库存在但元数据中不存在，系统必须记录 `table_added` 并插入元数据。
29. 同步必须使用差异更新（diff），不是全量覆盖：
    - 对比目标数据源当前 schema 与已存元数据
    - 检测变更类型：table_added、table_removed、column_added、column_removed、column_modified、index_added、index_removed、fk_added、fk_removed
    - 先写 `metadata_change_logs`，再更新元数据表
30. 同步失败时必须记录错误信息到 `metadata_sync_logs.error_message`，不影响已存储的元数据。
31. 同一 data_source 同一时刻仅允许一个 status=running 的 sync_log。如果已有 running 记录，新的同步请求必须返回 HTTP 409 Conflict。

### 查询接口

32. 系统必须提供 `GET /api/datasources/{id}/metadata` 返回元数据概览（表数量、字段数量等）。
33. 系统必须提供 `GET /api/datasources/{id}/sync-logs` 返回同步日志列表。

## 业务规则

### 连接安全

- 数据源密码使用 Fernet 对称加密存储，密钥通过 `.env` 的 `ENCRYPTION_KEY` 配置（必须配置，无默认值）
- 目标数据源连接强制只读
- 查询超时保护
- API 响应中永不返回密码明文

### 激活规则

- 同一时刻全局仅一条 `is_active = true`
- 激活新数据源 → 自动停用旧数据源 → dispose 旧引擎
- 激活时若无元数据 → 异步触发首次全量提取 → API 立即返回 → 后台创建 sync_log (type=full, status=running)
- 删除数据源 → 级联删除所有关联元数据（ON DELETE CASCADE）

### 同步规则

- 定时同步：全量，间隔可配置
- 手动同步：全量或指定表（table_scope）
- 差异更新，非全量覆盖
- 并发防护：同一 data_source 仅一个 running sync_log
- 失败时记录错误，不影响已有数据

### PG vs MySQL 适配

| 差异点 | PostgreSQL | MySQL |
|--------|------------|-------|
| schema 概念 | `schema_name` | `TABLE_SCHEMA` = database name |
| 注释来源 | `pg_catalog.pg_description` | `information_schema.TABLES.TABLE_COMMENT` |
| 索引查询 | `pg_catalog.pg_indexes` | `information_schema.STATISTICS` |
| 只读设置 | `SET TRANSACTION READ ONLY` | `SET SESSION TRANSACTION READ ONLY` |
| 超时设置 | `statement_timeout` | `max_execution_time` |
| 异步驱动 | asyncpg | asyncmy |
| 表类型 | `table_type` 字段 | `table_type` 字段 |

## 边界情况与错误状态

| 场景 | 预期行为 |
|------|----------|
| 激活数据源时目标库不可达 | API 正常返回（激活成功），后台首次提取创建 sync_log (status=failed, error_message 包含连接错误) |
| 同步过程中目标库连接断开 | sync_log 记录 status=failed + error_message，已写入的部分 change_log 保留 |
| 手动同步时指定的表在目标库不存在 | 记录 table_removed 变更日志，删除该表的已存元数据 |
| 手动同步时指定的表在目标库存在但元数据中不存在 | 记录 table_added 变更日志，插入该表的元数据 |
| 同时触发两次手动同步（同一数据源） | 第二次请求返回 HTTP 409 Conflict |
| 删除激活的数据源 | 级联删除所有元数据，dispose 引擎 |
| `.env` 中未配置 `ENCRYPTION_KEY` | 创建/更新数据源时返回 500，日志记录密钥缺失 |
| `schema_whitelist` 中的 schema 在目标库不存在 | 跳过该 schema，不报错 |
| 空数据库（目标库无任何用户表） | 正常完成，metadata_tables 无记录，sync_log 显示 tables_added=0 |

## 数据与状态

### 数据对象

**`data_sources`** — 数据源配置

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| name | VARCHAR(100) | UNIQUE, NOT NULL | 显示名称 |
| engine | ENUM('postgresql', 'mysql') | NOT NULL | |
| host | VARCHAR(255) | NOT NULL | |
| port | INTEGER | NOT NULL | |
| username | VARCHAR(100) | NOT NULL | |
| password_encrypted | TEXT | NOT NULL | Fernet 加密 |
| database | VARCHAR(100) | NOT NULL | |
| schema_whitelist | JSONB | | null = 全部非系统 |
| is_active | BOOLEAN | NOT NULL, DEFAULT false | 全局唯一 true |
| created_at | TIMESTAMP | NOT NULL | |
| updated_at | TIMESTAMP | NOT NULL | |

**`metadata_tables`** — 表级元数据

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| data_source_id | UUID | FK → data_sources.id ON DELETE CASCADE, NOT NULL | |
| schema_name | VARCHAR(100) | NOT NULL | |
| table_name | VARCHAR(100) | NOT NULL | |
| table_type | VARCHAR(20) | NOT NULL, DEFAULT 'BASE TABLE' | BASE TABLE / VIEW / MATERIALIZED VIEW |
| table_comment | TEXT | | |
| created_at | TIMESTAMP | NOT NULL | |
| updated_at | TIMESTAMP | NOT NULL | |

UNIQUE: `(data_source_id, schema_name, table_name)`

**`metadata_columns`** — 字段级元数据

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| table_id | UUID | FK → metadata_tables.id ON DELETE CASCADE, NOT NULL | |
| column_name | VARCHAR(100) | NOT NULL | |
| data_type | VARCHAR(50) | NOT NULL | |
| is_nullable | BOOLEAN | NOT NULL | |
| default_value | TEXT | | |
| column_comment | TEXT | | |
| is_primary_key | BOOLEAN | NOT NULL, DEFAULT false | |
| ordinal_position | INTEGER | NOT NULL | |

UNIQUE: `(table_id, column_name)`

**`metadata_indexes`** — 索引元数据

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| table_id | UUID | FK → metadata_tables.id ON DELETE CASCADE, NOT NULL | |
| index_name | VARCHAR(100) | NOT NULL | |
| column_names | JSONB | NOT NULL | 关联字段列表 |
| is_unique | BOOLEAN | NOT NULL | |

UNIQUE: `(table_id, index_name)`

**`metadata_foreign_keys`** — 外键元数据

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| table_id | UUID | FK → metadata_tables.id ON DELETE CASCADE, NOT NULL | |
| constraint_name | VARCHAR(100) | NOT NULL | |
| column_name | VARCHAR(100) | NOT NULL | 来源字段 |
| target_schema | VARCHAR(100) | NOT NULL | |
| target_table | VARCHAR(100) | NOT NULL | |
| target_column | VARCHAR(100) | NOT NULL | |

UNIQUE: `(table_id, constraint_name)`

**`metadata_sync_logs`** — 同步执行记录

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| data_source_id | UUID | FK → data_sources.id ON DELETE CASCADE, NOT NULL | |
| sync_type | ENUM('full', 'manual') | NOT NULL | |
| scope | JSONB | | 手动同步时的表范围，null = 全量 |
| status | ENUM('running', 'success', 'failed') | NOT NULL | |
| started_at | TIMESTAMP | NOT NULL | |
| finished_at | TIMESTAMP | | |
| tables_added | INTEGER | | |
| tables_removed | INTEGER | | |
| columns_changed | INTEGER | | |
| error_message | TEXT | | |

**`metadata_change_logs`** — 具体变更条目

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| sync_log_id | UUID | FK → metadata_sync_logs.id ON DELETE CASCADE, NOT NULL | |
| data_source_id | UUID | FK → data_sources.id ON DELETE CASCADE, NOT NULL | |
| change_type | ENUM('table_added', 'table_removed', 'column_added', 'column_removed', 'column_modified', 'index_added', 'index_removed', 'fk_added', 'fk_removed') | NOT NULL | |
| schema_name | VARCHAR(100) | NOT NULL | |
| table_name | VARCHAR(100) | NOT NULL | |
| object_name | VARCHAR(100) | | 字段/索引/外键名 |
| before_value | JSONB | | |
| after_value | JSONB | | |

### 数据库迁移

使用 Alembic 管理应用 PostgreSQL 的 schema 变更。

## 权限与合规

- Phase 1 无用户系统，所有数据源管理 API 暂不鉴权（TODO: Phase 9 补齐）
- 数据源连接密码加密存储，API 永不返回明文
- 目标数据源连接强制只读，系统不修改用户数据
- 同步日志和变更日志提供完整审计追踪

## 发布与运营

### 依赖变更

`pyproject.toml` 需添加：

| 包 | 用途 |
|------|------|
| `asyncmy` | MySQL 异步驱动 |
| `cryptography` | Fernet 对称加密 |
| `alembic` | 数据库迁移管理 |
| `apscheduler` | 定时同步调度 |

### 配置变更

`.env.example` 需添加：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `ENCRYPTION_KEY` | 数据源密码加密密钥 | 无（必须配置） |
| `METADATA_SYNC_INTERVAL_HOURS` | 同步间隔（小时） | 24 |

### 迁移

- 首次部署：运行 `alembic upgrade head` 创建 7 张新表
- 无历史数据迁移需求（新系统）

### 监控

- 同步延迟：通过 `metadata_sync_logs` 的 `started_at` 和 `finished_at` 监控
- 同步失败：通过 `status = 'failed'` 监控
- Phase 1 仅日志记录，Phase 10 管理端面板可视化展示

## 实现决策

### 模块划分

| 包 | 职责 |
|------|------|
| `src/config/` | 应用配置（.env → pydantic-settings），新增 `ENCRYPTION_KEY` 和 `METADATA_SYNC_INTERVAL_HOURS` |
| `src/db/` | 数据源连接管理（只读引擎创建/缓存/dispose），PG 和 MySQL 双引擎支持 |
| `src/metadata/` | 元数据提取（PG/MySQL 适配器）、存储（SQLAlchemy ORM 模型）、同步引擎（diff 计算 + APScheduler 调度） |
| `src/api/` | 数据源配置 CRUD + 连接测试 + 激活/同步/元数据查询 API |

### 关键接口

- `DataSourceManager`：数据源 CRUD + 加密/解密 + 引擎缓存
- `MetadataExtractor`（Protocol）：PG 和 MySQL 各一个实现，提取 information_schema
- `SyncEngine`：diff 计算 + 变更日志 + 元数据更新
- `SyncScheduler`：APScheduler 封装，定时 + 手动触发

### 架构约束

- 连接层通过 SQLAlchemy dialect 抽象，上层代码不感知 PG/MySQL 差异
- 外部依赖（LLM、向量库、图数据库、缓存、数据库）通过 Protocol/Base Class 访问
- 新增行为通过策略/插件模式扩展，不修改已有分发器（OCP）

## 测试决策

### 自动化测试

- **数据源配置 CRUD**：测试创建/读取/更新/删除，验证加密存储、密码不返回、唯一名称约束
- **连接测试 API**：mock 数据库连接，测试成功和失败场景
- **激活逻辑**：测试单激活约束、引擎创建/dispose、首次提取触发
- **元数据提取**：mock information_schema 查询结果，验证 PG 和 MySQL 提取器的字段映射
- **同步引擎**：测试 diff 计算（新增表、删除表、字段变更）、变更日志记录、并发防护（HTTP 409）
- **表级同步**：测试 table_scope 参数，验证仅检查指定表

### 手工验收

- 连接真实 PostgreSQL 数据库，执行完整提取流程
- 连接真实 MySQL 数据库，执行完整提取流程
- 在目标库中添加/删除/修改表，执行同步，验证变更日志
- 激活不同数据源，验证切换行为

## 验收标准

### 数据源配置

- Given 无数据源，When 创建 PG 数据源配置，Then 成功返回，密码加密存储
- Given 已有数据源 A，When 创建同名数据源，Then 返回错误
- Given 已有数据源 A（含密码），When 查询数据源列表，Then 响应不包含密码字段
- Given 已有数据源 A，When 测试连接且目标库可达，Then 返回成功
- Given 已有数据源 A，When 测试连接且目标库不可达，Then 返回失败和错误信息

### 激活与提取

- Given 数据源 A 未激活且无元数据，When 激活 A，Then API 立即返回，is_active=true，后台创建 running sync_log
- Given 激活数据源 A（提取完成），When 激活数据源 B，Then A 的 is_active=false，A 的引擎被 dispose
- Given 激活数据源 A（首次提取完成），When 查询元数据概览，Then 返回表数量和字段数量

### 同步

- Given 激活数据源有 10 张表，When 目标库新增 1 张表后执行同步，Then sync_log 显示 tables_added=1，change_log 有 table_added 记录
- Given 激活数据源有 10 张表，When 目标库删除 1 张表后执行同步，Then sync_log 显示 tables_removed=1，该表及其字段/索引/外键元数据被删除
- Given 激活数据源，When 手动同步指定 table_scope=[orders]，Then 仅检查 orders 表的字段/索引/外键变更
- Given 同步正在运行（sync_log status=running），When 再次触发同步，Then 返回 HTTP 409
- Given 同步过程中目标库断开，Then sync_log status=failed，error_message 包含错误信息

## 开放问题

（暂无）

## 补充说明

- 设计规格：`docs/自然语言数据库查询需求设计.md`（V5.0 最终版）
- 开发计划：`docs/development-plan.md`（12 阶段，本 PRD 对应 Phase 1）
- 产品决策 P-001：`team-spec/decisions/001-target-datasource-engine.md`
- 规格细化：`team-spec/active/2026-06-05-db-connection-metadata/spec/refine.md`
- 规格评审：`team-spec/active/2026-06-05-db-connection-metadata/spec/reviews.md`
