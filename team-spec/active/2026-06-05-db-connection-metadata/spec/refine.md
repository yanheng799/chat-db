# 数据源连接与元数据提取 — 规格细化

> slug: `2026-06-05-db-connection-metadata`
> 对应开发计划：Phase 1（1.1-1.4）+ 数据源配置管理（新增）

## 需求概述

建立系统连接目标数据库的基础能力：通过管理界面配置数据源（支持 PostgreSQL 和 MySQL），建立只读连接，从 `information_schema` 全量提取表/字段/索引/外键元数据，存入应用 PostgreSQL 数据库，并实现定时全量同步检测结构变更。

## 用户角色

| 角色 | 操作 |
|------|------|
| 管理员 | 添加/编辑/删除数据源配置，测试连接，激活数据源，手动触发同步，查看元数据提取结果，查看同步日志 |
| 系统（定时任务） | 按计划执行全量同步，检测变更，记录变更日志 |

## 功能范围

### 范围内（Phase 1）

1. **数据源配置管理**
   - 数据库模型：`data_sources` 表，存储引擎类型、连接参数（加密密码）、schema 白名单、激活状态等
   - CRUD API：增删改查数据源配置
   - 激活/停用：同一时刻仅一条配置为激活状态
   - 连接测试：独立的"测试连接"API 端点，保存时不自动测试

2. **只读数据库连接层**
   - 从数据库读取激活数据源配置，创建 SQLAlchemy async 引擎
   - 强制只读：PG 使用 `SET TRANSACTION READ ONLY`，MySQL 使用 `SET SESSION TRANSACTION READ ONLY`
   - 超时控制：PG 使用 `statement_timeout`，MySQL 使用 `max_execution_time`
   - 连接池管理：合理的池大小和超时配置
   - 支持 PG（asyncpg）和 MySQL（asyncmy）两种驱动

3. **元数据提取**
   - 从目标数据源的 `information_schema` 提取：
     - 表信息：schema、表名、表类型（TABLE/VIEW/MATERIALIZED VIEW）、注释
     - 字段信息：字段名、类型、是否可空、默认值、注释、是否主键、字段顺序
     - 索引信息：索引名、关联字段、是否唯一
     - 外键信息：来源字段、目标表、目标字段（仅显式声明的外键）
   - 不提取行数
   - 按 `data_source_id` 隔离存储
   - 激活数据源时**异步触发**首次提取（API 立即返回，后台执行）

4. **元数据存储**
   - 应用 PostgreSQL 中的表结构：
     - `metadata_tables`：表级信息，关联 `data_source_id`
     - `metadata_columns`：字段级信息，关联 `table_id`
     - `metadata_indexes`：索引信息，关联 `table_id`
     - `metadata_foreign_keys`：外键信息，关联 `table_id`
     - `metadata_sync_logs`：同步执行记录（时间、状态、变更统计）
     - `metadata_change_logs`：具体变更条目（类型、变更前、变更后）
   - 全量快照存储（每次同步覆盖对应 data_source 的元数据）
   - 数据库迁移使用 Alembic 管理

5. **定时全量同步 + 手动同步**
   - 定时扫描激活数据源的 `information_schema`（间隔通过 `.env` 的 `METADATA_SYNC_INTERVAL_HOURS` 配置，默认 24 小时）
   - 管理员可通过 API 手动触发同步
   - 与已存储元数据做 diff 比较
   - 检测：新增表、删除表、字段变更（增/删/改）、索引变更、外键变更
   - 更新元数据存储表
   - 记录变更日志
   - 调度器使用 APScheduler（进程内，Phase 1 足够）

### 明确排除

- 错误触发同步（Phase 7）
- 向量库和图谱更新（Phase 3）
- 元数据学习 L1/L2（Phase 2）
- 前端管理界面 UI（Phase 10 补齐，Phase 1 只做 API）
- 运行时多数据源切换（V1 之后）
- 行数提取和统计
- 数据采样（Phase 2 LLM 学习需要）
- API 鉴权（Phase 9 用户系统建立后统一处理）

## 数据模型

### `data_sources` 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| name | VARCHAR(100) | UNIQUE, NOT NULL | 数据源显示名称 |
| engine | ENUM('postgresql', 'mysql') | NOT NULL | 数据库引擎 |
| host | VARCHAR(255) | NOT NULL | 主机地址 |
| port | INTEGER | NOT NULL | 端口 |
| username | VARCHAR(100) | NOT NULL | 连接用户名 |
| password_encrypted | TEXT | NOT NULL | 加密后的密码 |
| database | VARCHAR(100) | NOT NULL | 目标数据库名 |
| schema_whitelist | JSONB | | schema 白名单（PG）或 database 白名单（MySQL），null 表示全部非系统 |
| is_active | BOOLEAN | NOT NULL, DEFAULT false | 是否激活（全局仅一条为 true） |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |
| updated_at | TIMESTAMP | NOT NULL | 更新时间 |

### `metadata_tables` 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| data_source_id | UUID | FK → data_sources.id, NOT NULL | 关联数据源 |
| schema_name | VARCHAR(100) | NOT NULL | schema 名称 |
| table_name | VARCHAR(100) | NOT NULL | 表名 |
| table_type | VARCHAR(20) | NOT NULL, DEFAULT 'BASE TABLE' | 表类型：BASE TABLE / VIEW / MATERIALIZED VIEW |
| table_comment | TEXT | | 表注释 |
| created_at | TIMESTAMP | NOT NULL | 首次提取时间 |
| updated_at | TIMESTAMP | NOT NULL | 最后更新时间 |

**唯一约束**：`UNIQUE (data_source_id, schema_name, table_name)`

### `metadata_columns` 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| table_id | UUID | FK → metadata_tables.id, NOT NULL | 关联表 |
| column_name | VARCHAR(100) | NOT NULL | 字段名 |
| data_type | VARCHAR(50) | NOT NULL | 数据类型 |
| is_nullable | BOOLEAN | NOT NULL | 是否可空 |
| default_value | TEXT | | 默认值 |
| column_comment | TEXT | | 字段注释 |
| is_primary_key | BOOLEAN | NOT NULL, DEFAULT false | 是否主键 |
| ordinal_position | INTEGER | NOT NULL | 字段顺序 |

**唯一约束**：`UNIQUE (table_id, column_name)`

### `metadata_indexes` 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| table_id | UUID | FK → metadata_tables.id, NOT NULL | 关联表 |
| index_name | VARCHAR(100) | NOT NULL | 索引名 |
| column_names | JSONB | NOT NULL | 关联字段列表 |
| is_unique | BOOLEAN | NOT NULL | 是否唯一索引 |

**唯一约束**：`UNIQUE (table_id, index_name)`

### `metadata_foreign_keys` 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| table_id | UUID | FK → metadata_tables.id, NOT NULL | 关联表（来源表） |
| constraint_name | VARCHAR(100) | NOT NULL | 外键约束名 |
| column_name | VARCHAR(100) | NOT NULL | 来源字段 |
| target_schema | VARCHAR(100) | NOT NULL | 目标 schema |
| target_table | VARCHAR(100) | NOT NULL | 目标表 |
| target_column | VARCHAR(100) | NOT NULL | 目标字段 |

**唯一约束**：`UNIQUE (table_id, constraint_name)`

### `metadata_sync_logs` 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| data_source_id | UUID | FK → data_sources.id, NOT NULL | 关联数据源 |
| sync_type | ENUM('full', 'manual') | NOT NULL | 同步类型 |
| scope | JSONB | | 手动同步时的表范围，格式：`[{"schema": "public", "table": "orders"}]`。null 表示全量 |
| status | ENUM('running', 'success', 'failed') | NOT NULL | 执行状态 |
| started_at | TIMESTAMP | NOT NULL | 开始时间 |
| finished_at | TIMESTAMP | | 结束时间 |
| tables_added | INTEGER | | 新增表数 |
| tables_removed | INTEGER | | 删除表数 |
| columns_changed | INTEGER | | 字段变更数 |
| error_message | TEXT | | 失败时的错误信息 |

### `metadata_change_logs` 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| sync_log_id | UUID | FK → metadata_sync_logs.id, NOT NULL | 关联同步记录 |
| data_source_id | UUID | FK → data_sources.id, NOT NULL | 关联数据源 |
| change_type | ENUM('table_added', 'table_removed', 'column_added', 'column_removed', 'column_modified', 'index_added', 'index_removed', 'fk_added', 'fk_removed') | NOT NULL | 变更类型 |
| schema_name | VARCHAR(100) | NOT NULL | schema |
| table_name | VARCHAR(100) | NOT NULL | 表名 |
| object_name | VARCHAR(100) | | 对象名（字段/索引/外键） |
| before_value | JSONB | | 变更前 |
| after_value | JSONB | | 变更后 |

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/datasources` | POST | 创建数据源配置 |
| `/api/datasources` | GET | 列出所有数据源配置（不含密码） |
| `/api/datasources/{id}` | GET | 获取单个数据源配置（不含密码） |
| `/api/datasources/{id}` | PUT | 更新数据源配置 |
| `/api/datasources/{id}` | DELETE | 删除数据源配置（同时删除关联元数据） |
| `/api/datasources/{id}/activate` | POST | 激活此数据源（自动停用其他，异步触发首次提取） |
| `/api/datasources/{id}/test` | POST | 测试数据源连接，返回成功/失败及错误信息 |
| `/api/datasources/{id}/sync` | POST | 手动触发同步（后台异步执行）。可选 body 参数 `table_scope`：表列表 `[{"schema": "public", "table": "orders"}]`，不传则全量同步 |
| `/api/datasources/{id}/metadata` | GET | 查看此数据源的元数据概览（表数量、字段数量等） |
| `/api/datasources/{id}/sync-logs` | GET | 查看同步日志列表 |

## 行为规则

### 连接安全

- 目标数据源连接强制只读（PG: `SET TRANSACTION READ ONLY`; MySQL: `SET SESSION TRANSACTION READ ONLY`）
- 超时控制（PG: `statement_timeout`; MySQL: `max_execution_time`）
- 连接密码使用对称加密存储（Fernet），密钥通过 `.env` 的 `ENCRYPTION_KEY` 配置
- API 响应中永不返回密码明文

### 连接池生命周期

- 激活数据源时创建 SQLAlchemy async 引擎
- 停用数据源时 dispose 对应引擎
- 应用关闭时 dispose 所有引擎
- 引擎缓存：以 `data_source_id` 为 key 缓存引擎实例，避免重复创建

### 提取范围

- PG 默认排除系统 schema：`pg_catalog`、`information_schema`、`pg_toast` 及所有 `pg_temp_*`
- MySQL 默认排除系统 database：`mysql`、`information_schema`、`performance_schema`、`sys`
- 用户可通过 `schema_whitelist` 指定只提取特定 schema/database
- `schema_whitelist` 为 null 时提取所有非系统 schema/database

### 激活逻辑

- 同一时刻全局仅一条数据源配置为 `is_active = true`
- 激活新数据源时，自动停用原激活数据源（dispose 旧引擎）
- 激活时如果该数据源尚无元数据，**异步触发首次全量提取**
  - activate API 立即返回
  - 后台创建 sync_log（type=full, status=running）
  - 提取完成后更新 sync_log（status=success/failed）
  - 管理员通过 `GET /api/datasources/{id}/sync-logs` 查看进度
- 删除激活数据源时，同时删除其所有元数据（级联删除）

### 同步逻辑

- 定时扫描激活数据源（间隔通过 `.env` 的 `METADATA_SYNC_INTERVAL_HOURS` 配置，默认 24）
- 管理员可通过 `POST /api/datasources/{id}/sync` 手动触发
  - **全量同步**：不传 `table_scope`，检查所有表的 schema 变更
  - **表级同步**：传 `table_scope` 表列表，仅检查指定表的 schema 变更（增量检查）
  - 表级同步检查范围：指定表的字段（增/删/改）、索引（增/删）、外键（增/删）
  - 如果指定表在目标库中已不存在，记录 `table_removed` 变更日志
- 全量对比：目标数据源 information_schema vs 已存储元数据
- 检测变更类型：表增/删、字段增/删/改、索引增/删、外键增/删
- 先写 `metadata_change_logs`，再更新元数据表
- 同步失败时记录错误信息，不影响已存储的元数据
- 调度器使用 APScheduler（进程内，Phase 1 足够）

### PG vs MySQL 适配

| 差异点 | PostgreSQL | MySQL |
|--------|------------|-------|
| schema 概念 | `schema_name` in `information_schema.tables` | `TABLE_SCHEMA` = database name |
| 注释来源 | `pg_catalog.pg_description` | `information_schema.TABLES.TABLE_COMMENT` |
| 索引查询 | `pg_catalog.pg_indexes` | `information_schema.STATISTICS` |
| 只读设置 | `SET TRANSACTION READ ONLY` | `SET SESSION TRANSACTION READ ONLY` |
| 超时设置 | `statement_timeout` | `max_execution_time` |
| 异步驱动 | asyncpg | asyncmy |
| 表类型 | `information_schema.tables.table_type` | `information_schema.tables.table_type` |

## 依赖变更

以下依赖需要在 `pyproject.toml` 中添加：

| 包 | 用途 |
|------|------|
| `asyncmy` | MySQL 异步驱动（SQLAlchemy async） |
| `cryptography` | Fernet 对称加密（数据源密码加密） |
| `alembic` | 数据库迁移管理 |
| `apscheduler` | 定时同步调度 |

以下配置项需要在 `.env.example` 中添加：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `ENCRYPTION_KEY` | 数据源密码加密密钥（Fernet key） | 无（必须配置） |
| `METADATA_SYNC_INTERVAL_HOURS` | 元数据同步间隔（小时） | 24 |

## 开放问题

（暂无）

## 风险

1. **PG 注释获取**：PostgreSQL 的表/字段注释不在标准 `information_schema` 中，需要额外查询 `pg_catalog.pg_description`，提取逻辑比 MySQL 更复杂
2. **加密密钥管理**：密钥丢失意味着所有数据源密码不可恢复，需要密钥轮换机制或备份策略
3. **大数据量提取**：目标数据源有数千张表时，全量提取和同步可能耗时较长，需要考虑提取超时
4. **API 鉴权缺失**：Phase 1 无用户系统，数据源管理 API 暂不鉴权（PRD 标注 TODO，Phase 9 补齐）

## 产品决策

| 编号 | 决策 | 文档 |
|------|------|------|
| P-001 | 目标数据源支持 PG + MySQL，配置存数据库，前端管理 | [decisions/001](decisions/001-target-datasource-engine.md) |

## Change Log

| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-06-05 | 手动同步支持表级选择：增加 table_scope 参数、metadata_sync_logs 增加 scope 字段、更新同步逻辑规则 | 用户新增需求 |
| 2026-06-05 | 增加 table_type 字段；补充所有 metadata 表唯一约束；首次提取改为异步后台；增加手动同步 API；增加连接池生命周期规则；明确 MySQL 驱动为 asyncmy、调度器为 APScheduler、迁移为 Alembic；补充依赖变更和配置项；增加 API 鉴权 TODO | 响应评审 P1/P2 项 |
| 2026-06-05 | 初始创建 | 需求细化首轮 |
