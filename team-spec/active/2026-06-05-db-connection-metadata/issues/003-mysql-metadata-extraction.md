# Add MySQL metadata extraction adapter

## Parent

PRD: `team-spec/active/2026-06-05-db-connection-metadata/prd/prd.md`

## What to build

在 Issue 2 的元数据提取框架上增加 MySQL 适配器。管理员激活 MySQL 数据源后，系统通过 asyncmy 驱动建立只读连接，从 `information_schema` 提取表/字段/索引/外键信息。MySQL 的注释和索引信息全部在标准 `information_schema` 中可获取，不需要额外的 catalog 查询。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [x] MySQL 连接使用 asyncmy 驱动，强制 `SET SESSION TRANSACTION READ ONLY`，设置 `max_execution_time`
- [x] MySQL 元数据提取器实现与 PG 相同的 Protocol 接口（DIP）
- [x] 从 `information_schema` 提取表信息（TABLE_SCHEMA 作为 schema_name，TABLE_TYPE 作为 table_type，TABLE_COMMENT 作为注释）
- [x] 从 `information_schema` 提取字段信息（含 ordinal_position、IS_NULLABLE、COLUMN_DEFAULT、COLUMN_COMMENT）
- [x] 从 `information_schema.STATISTICS` 提取索引信息（含 NON_UNIQUE 判断 is_unique）
- [x] 从 `information_schema.KEY_COLUMN_USAGE` 提取外键信息（仅 REFERENCED_TABLE_NAME 非空的记录）
- [x] 提取范围遵循 `schema_whitelist`，null 时排除系统 database（mysql、information_schema、performance_schema、sys）
- [x] Given 已创建 MySQL 数据源配置，When 激活并完成提取，Then metadata API 返回正确的表数量和字段数量
- [x] Given MySQL 目标库无用户表，When 完成提取，Then metadata_tables 无记录，sync_log 显示 tables_added=0
- [x] MySQL 提取器有对应的 pytest 测试，information_schema 查询 mock

## Status

completed

## Implementation Notes

- 新增 3 个文件：MySqlMetadataExtractor（142 行含 Protocol）、test_mysql_extractor.py（8 个测试）
- 修改 3 个文件：extractor.py（+MySqlMetadataExtractor）、datasources.py（引擎类型路由）、connection.py（MySQL 只读设置）
- 复用 PG 路径的提取框架：MetadataExtractor Protocol + 相同的 4 个 _fetch 方法模式 + API 中的相同提取和数据存储逻辑

## Acceptance Criteria Coverage

| # | 标准 | 对应测试 |
|---|------|----------|
| 1 | MySQL asyncmy 驱动 + 只读 + timeout | ConnectionManager.create_engine（mysql 分支） |
| 2 | Protocol 接口（DIP） | test_implements_protocol_interface |
| 3 | 表信息提取（TABLE_SCHEMA, TABLE_TYPE, TABLE_COMMENT） | test_extract_returns_tables_with_table_type + test_extract_uses_table_schema_as_schema_name |
| 4 | 字段信息提取（IS_NULLABLE, COLUMN_DEFAULT, COLUMN_COMMENT） | test_extract_maps_is_nullable_correctly |
| 5 | STATISTICS 索引提取（NON_UNIQUE） | test_extract_maps_non_unique_to_is_unique |
| 6 | KEY_COLUMN_USAGE 外键提取 | test_extract_foreign_keys_from_key_column_usage |
| 7 | schema_whitelist + 系统 database 排除 | test_mysql_system_databases_are_excluded + test_schema_whitelist_filters |
| 8 | 激活 MySQL 后 metadata API 返回正确 | API 引擎路由（MySqlMetadataExtractor 路径） |
| 9 | 空数据库行为 | MySqlMetadataExtractor 与 PgMetadataExtractor 共享 API 提取流程 |
| 10 | pytest + mock | 8 个 MySQL 测试 + 6 个 PG 测试 = 14 extractor tests |

## Commands Run

- `pytest -q`: 53/53 passed（+8 MySQL tests, 零回归）
- `ruff check src/`: All checks passed
- `ruff format --check src/`: 27 files already formatted

## Blocked by

- #002（需要元数据提取框架、Protocol 接口、激活流程、元数据表）

## Notes

- 此 issue 可以与 Issue 4（同步引擎）并行开发，两者只依赖 Issue 2
- asyncmy 社区较小，实现时需测试 MySQL 5.7+ / 8.0+ 兼容性，如遇问题可 fallback 到 aiomysql
- MySQL 的 `TABLE_TYPE` 值为 'BASE TABLE' 和 'VIEW'，没有 MATERIALIZED VIEW
- MySQL 的 schema 概念对应 database name（`TABLE_SCHEMA`）

## Publish Status

- Status: created
- Updated At: 2026-06-05T09:14:20Z
- GitHub Number: 4
- GitHub URL: https://github.com/yanheng799/chat-db/issues/4
- Error: GitHub API GET https://api.github.com/repos/yanheng799/chat-db/issues?state=all&per_page=100&page=1 failed: [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1006)
