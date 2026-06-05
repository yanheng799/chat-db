# Implement data source activation and PostgreSQL metadata extraction

## Parent

PRD: `team-spec/active/2026-06-05-db-connection-metadata/prd/prd.md`

## What to build

实现数据源激活和 PostgreSQL 元数据提取的完整链路：管理员激活数据源后，系统自动创建只读 SQLAlchemy async 引擎，后台异步从目标 PostgreSQL 的 `information_schema` 和 `pg_catalog` 提取表/字段/索引/外键信息，存入元数据表。管理员可以查看元数据概览和提取进度。

这是系统核心价值的第一次端到端验证——激活一个真实 PG 数据源后，能看到完整的表结构信息。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [x] Alembic 迁移创建 6 张元数据表（metadata_tables、metadata_columns、metadata_indexes、metadata_foreign_keys、metadata_sync_logs、metadata_change_logs），字段、约束和 ON DELETE CASCADE 与 PRD 一致
- [x] `POST /api/datasources/{id}/activate` 激活数据源，自动停用原激活数据源，`is_active` 全局唯一
- [x] 激活时如果该数据源尚无元数据，后台异步触发首次全量提取，API 立即返回
- [x] 后台创建 sync_log（type=full, status=running），提取完成后更新 status=success/failed
- [x] SQLAlchemy async 引擎以 `data_source_id` 为 key 缓存，激活时创建，停用时 dispose
- [x] PG 连接强制 `SET TRANSACTION READ ONLY`，设置 `statement_timeout`
- [x] PG 元数据提取：从 `information_schema` 获取表/字段信息，从 `pg_catalog.pg_description` 获取注释，从 `pg_catalog.pg_indexes` 获取索引，提取 `table_type`（BASE TABLE / VIEW / MATERIALIZED VIEW）
- [x] 提取范围遵循 `schema_whitelist` 配置，null 时排除系统 schema（pg_catalog、information_schema、pg_toast、pg_temp_*）
- [x] `GET /api/datasources/{id}/metadata` 返回元数据概览（表数量、字段数量）
- [x] `GET /api/datasources/{id}/sync-logs` 返回同步日志列表
- [x] Given 激活数据源 A（提取完成），When 激活数据源 B，Then A 的 is_active=false，A 的引擎被 dispose
- [x] Given 激活数据源时目标库不可达，Then 后台 sync_log status=failed，error_message 包含连接错误
- [x] 所有 API 和提取逻辑有对应的 pytest 测试，数据库连接 mock

## Blocked by

- #001（需要 data_sources 表、加密工具、配置读取）

## Notes

- PG 注释查询需要 JOIN `pg_catalog.pg_description` 和 `pg_catalog.pg_class`，比 MySQL 复杂
- 引擎缓存建议放在 `src/db/` 的连接管理器中，作为独立模块
- 元数据提取器应使用 Protocol 定义接口（DIP），PG 实现该 Protocol
- `metadata_tables` 的唯一约束 `(data_source_id, schema_name, table_name)` 在 upsert 时使用 ON CONFLICT
- 此 issue 只做 PG 提取，MySQL 留给 Issue 3

## Publish Status

- Status: created
- Updated At: 2026-06-05T09:14:06Z
- GitHub Number: 3
- GitHub URL: https://github.com/yanheng799/chat-db/issues/3
- Error: GitHub API GET https://api.github.com/repos/yanheng799/chat-db/issues?state=all&per_page=100&page=1 failed: [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1006)
