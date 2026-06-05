# Implement scheduled and manual metadata sync with table-level selection

## Parent

PRD: `team-spec/active/2026-06-05-db-connection-metadata/prd/prd.md`

## What to build

实现元数据同步引擎：定时全量同步、手动同步（全量或指定表）、差异计算、变更日志记录、并发防护。管理员在目标库 schema 变更后，可以通过手动同步 API 立即更新元数据，也可以等待定时同步自动检测变更。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [x] APScheduler 进程内调度，按 `METADATA_SYNC_INTERVAL_HOURS` 配置间隔（默认 24 小时）执行定时全量同步
- [x] `POST /api/datasources/{id}/sync` 手动触发同步（后台异步执行）
- [x] 不传 `table_scope` 时全量同步（检查所有表的 schema 变更）
- [x] 传 `table_scope` 时仅检查指定表的字段/索引/外键变更（增量检查）
- [x] 差异更新逻辑：对比目标库 information_schema 与已存元数据，检测 table_added / table_removed / column_added / column_removed / column_modified / index_added / index_removed / fk_added / fk_removed
- [x] 先写 `metadata_change_logs`，再更新元数据表
- [x] `metadata_sync_logs` 记录 scope 字段（null=全量，数组=表级），以及 tables_added / tables_removed / columns_changed 统计
- [x] 同一 data_source 同一时刻仅允许一个 status=running 的 sync_log，冲突时返回 HTTP 409
- [x] 同步失败时记录 error_message，status=failed，不影响已存元数据
- [x] Given 激活数据源有 10 张表，When 目标库新增 1 张表后执行同步，Then sync_log 显示 tables_added=1，change_log 有 table_added 记录
- [x] Given 激活数据源有 10 张表，When 目标库删除 1 张表后执行同步，Then sync_log 显示 tables_removed=1，该表及其字段/索引/外键元数据被删除
- [x] Given 同步正在运行，When 再次触发同步，Then 返回 HTTP 409
- [x] Given 手动同步指定 table_scope=[orders]，When 目标库 orders 表新增 1 个字段，Then 仅检查 orders 表，change_log 有 column_added 记录
- [x] 同步引擎有对应的 pytest 测试，diff 计算和并发防护有独立测试

## Status

completed

## Implementation Notes

- 新增 3 个文件：src/metadata/sync.py（差异引擎）、test/test_metadata/test_diff.py（10 个测试）、test/test_api/test_sync.py（4 个测试）
- 修改 2 个文件：src/api/datasources.py（sync 端点 + _run_sync + _build_stored_metadata + _apply_changes）、src/api/schemas.py（SyncRequest/SyncResponse/TableScopeItem）
- 差异引擎是纯函数，9 种变更类型全覆盖测试
- 手动同步 202 接受，后台异步执行；并发防护 409
- 定时同步通过 APScheduler 集成（由应用生命周期管理）

## Blocked by

- #002（需要元数据表、提取器框架、激活流程）

## Notes

- 此 issue 可以与 Issue 3（MySQL 适配器）并行开发，两者只依赖 Issue 2
- 差异计算是核心逻辑，建议提取为独立的纯函数（输入：当前 schema + 已存元数据，输出：变更列表），便于测试
- APScheduler 使用 BackgroundScheduler，与 FastAPI 生命周期绑定（startup 启动，shutdown 关闭）
- 定时同步的 scope 字段始终为 null（全量），sync_type 为 'full'
- 手动同步的 sync_type 为 'manual'，scope 取决于是否传了 table_scope

## Publish Status

- Status: skipped
- Updated At: 2026-06-05T09:14:26Z
- GitHub Number: 1
- GitHub URL: https://github.com/yanheng799/chat-db/issues/1
