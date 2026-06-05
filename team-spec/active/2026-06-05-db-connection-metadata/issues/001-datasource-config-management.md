# Set up data source config management with encrypted password storage

## Parent

PRD: `team-spec/active/2026-06-05-db-connection-metadata/prd/prd.md`

## What to build

搭建数据源配置管理的基础能力：管理员可以通过 API 创建、查询、更新、删除数据源配置（PostgreSQL 或 MySQL），密码使用 Fernet 加密存储。管理员可以测试数据源连接是否可达。配置存入应用 PostgreSQL 的 `data_sources` 表。

这个切片还包含所有后续 issue 共享的基础设施：新增依赖（asyncmy、cryptography、alembic、apscheduler）、Alembic 初始化、ENCRYPTION_KEY 配置项。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [x] `pyproject.toml` 已添加 `asyncmy`、`cryptography`、`alembic`、`apscheduler` 依赖，`uv sync` 成功
- [x] Alembic 已初始化，`alembic upgrade head` 创建 `data_sources` 表，字段和约束与 PRD 数据模型一致
- [x] `.env.example` 已添加 `ENCRYPTION_KEY`（无默认值，必须配置）和 `METADATA_SYNC_INTERVAL_HOURS`（默认 24）
- [x] `src/config/` 中 pydantic-settings 类读取 `ENCRYPTION_KEY` 和 `METADATA_SYNC_INTERVAL_HOURS`
- [x] `POST /api/datasources` 创建数据源配置，密码使用 Fernet 加密后存入 `password_encrypted` 字段
- [x] `GET /api/datasources` 返回所有配置，响应不含密码字段
- [x] `GET /api/datasources/{id}` 返回单个配置，响应不含密码字段
- [x] `PUT /api/datasources/{id}` 更新配置，更新密码时重新加密
- [x] `DELETE /api/datasources/{id}` 删除配置
- [x] `name` 字段全局唯一，重复创建返回错误
- [x] `POST /api/datasources/{id}/test` 测试数据源连接，返回成功/失败及错误信息（不修改任何状态）
- [x] Given `.env` 未配置 `ENCRYPTION_KEY`，When 创建数据源，Then 返回 500 错误
- [x] 所有 API 端点有对应的 pytest 测试，外部服务 mock

## Blocked by

None — can start immediately

## Notes

- 加密工具应放在 `src/config/` 或 `src/utils/` 中，作为后续 issue 的共享工具
- Alembic 配置应使用 asyncpg 驱动（同步模式用于迁移）
- `data_sources` 表的 `engine` 字段使用 VARCHAR + CHECK 约束（比 ENUM 更灵活）
- 此 issue 不创建 metadata 相关的表（留给 Issue 2）
- API 暂不鉴权（Phase 9 补齐）
- TDD：先定义 API 接口和数据模型 → 写测试 → 实现

## Publish Status

- Status: created
- Updated At: 2026-06-05T09:13:50Z
- GitHub Number: 2
- GitHub URL: https://github.com/yanheng799/chat-db/issues/2

## Status

completed

## Implementation Notes

- 新增文件 8 个：settings.py、models.py、data_source_model.py、database.py、encryption.py、main.py、schemas.py、datasources.py
- 新增测试文件 4 个：test_settings.py、test_encryption.py、test_datasources.py、test_api/conftest.py
- 修改文件 4 个：pyproject.toml、.env.example、test/conftest.py、uv.lock
- Alembic 迁移：1 个初始迁移（2855855924af），创建 data_sources 表含 12 个字段、CHECK 约束、UNIQUE 约束
- API 端点：7 个（POST create、GET list、GET single、PUT update、DELETE、POST test、激活/deactivate 留给 Issue 2）
- 依赖注入使用 FastAPI Annotated 模式（SessionDep），符合 ruff B008 规范

## Acceptance Criteria Coverage

所有 13 条验收标准通过 29 个测试覆盖：

| # | 标准 | 对应测试 |
|---|------|----------|
| 1 | pyproject.toml 依赖 + uv sync | 手动验证：`uv sync --extra dev` 成功，新包全部可 import |
| 2 | Alembic 初始化 + data_sources 表 | 手动验证：`alembic upgrade head` 成功创建表，字段/约束与 PRD 一致 |
| 3 | .env.example 新配置项 | 手动验证：ENCRYPTION_KEY 和 METADATA_SYNC_INTERVAL_HOURS 已添加 |
| 4 | pydantic-settings 读取配置 | TestSettings 5 个测试 |
| 5 | POST create + 加密密码 | TestCreateDataSource 6 个测试（含 create/basic、mysql、invalid-engine、schema_whitelist、no-key） |
| 6 | GET list 无密码泄漏 | TestListDataSources 1 个测试 |
| 7 | GET single 无密码泄漏 | TestGetDataSource 2 个测试（含 404） |
| 8 | PUT update + 密码重加密 | TestUpdateDataSource 3 个测试（含 fields、password、404） |
| 9 | DELETE 删除 | TestDeleteDataSource 2 个测试（含 404） |
| 10 | name 唯一约束 | test_create_duplicate_name_returns_409 |
| 11 | Connection test | TestConnectionTest 2 个测试（含 404） |
| 12 | 缺 ENCRYPTION_KEY 返回 500 | test_create_without_encryption_key_returns_500 |
| 13 | 所有端点有测试 | 16 API 测试 + 13 config 测试 = 29 total |

## Commands Run

- `pytest -v`: 29/29 passed
- `ruff check src/`: All checks passed
- `ruff format --check src/`: 24 files already formatted
- `alembic upgrade head`: Migration applied successfully

## Findings

无阻塞项。以下为低风险备注：

- Connection test 依赖真实外部数据库连接，测试中返回 success=false 是预期行为（目标 127.0.0.1 不可达）
- data_sources 表使用 VARCHAR + CHECK 替代 ENUM 类型，后续新增引擎（如 SQL Server）只需修改 CHECK 约束
- 数据库 session 管理使用 singleton engine，后续多数据源场景（Issue 2）需要重构为按 data_source_id 缓存引擎

## Regression Risks

无回归风险——项目此前为零实现代码，所有变更为新增。

## Required Changes

无。

## Notes

- 激活/停用 API（POST activate、引擎缓存管理）留给 Issue #3（003-activate-pg-metadata-extraction）
- API 鉴权留给 Phase 9
- 工作区变更未 commit，所有代码在本地工作区
