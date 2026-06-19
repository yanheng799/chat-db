# 创建枚举别名、区域字典、名称简称的存储表与 CRUD API

## Parent

PRD：`team-spec/active/2026-06-19-query-value-normalization/prd/prd.md`（收编的 3.5 值映射中心，issue F）

## What to build

创建 3 张值映射存储表的 Alembic 迁移 + CRUD API，作为枚举/区域/名称标准化器的**数据后端**：
- **枚举别名表** `value_enum_mappings`：`(data_source_id, table, column, value, display, aliases JSONB)`，唯一约束按源列值。
- **区域字典表** `value_region_dict`：`(data_source_id, code, parent_code, level, name, aliases JSONB)`。
- **名称简称表** `value_name_mappings`：`(data_source_id, short_name, full_name, aliases JSONB)`，唯一约束按源简称。
- 所有表按 `data_source_id` 隔离。CRUD API：单条增删改 + 批量导入。激活数据源时自动导入区域 CSV 种子；首次学习后自动从 Phase 1 `detected_enum_values` 采集枚举种子（value=原始值，display=原始值，aliases=空）；删除数据源时清理该源的全部映射。

## Type

AFK（可独立执行，无需人工决策）—— schema / API 端点 / 种子策略 已在 PRD 钉死。

## Acceptance criteria

- [x] Given Alembic 迁移，When `upgrade head`，Then 3 张映射表创建成功，含 `data_source_id` 外键 CASCADE 与唯一约束。
- [x] Given upsert 一条枚举别名，When list，Then 返回该记录。
- [x] Given upsert 更新 display，When list，Then display 已更新（幂等 upsert）。
- [x] Given cleanup_mappings，When 删除 DS，Then 三表记录清零。
- [x] Given `detected_enum_values` 非空的列，When `auto_collect_enum_seeds`，Then 枚举别名表新增对应记录（value=原始值，display=原始值，aliases=[]）。
- [ ] 区域 CSV 导入（预置 CSV 格式待实现——#26 标注）
- [x] 迁移 `b2d3e4f5a6c7` → `a1c7e9f40b2d`，可正反向。

## Blocked by

- None - can start immediately

## Notes

- 区域 CSV 格式：4 列 `code,parent_code,level,name`，无 header，UTF-8。`parent_code` 空表示顶级，`level` 取值 `province/city/district`。
- 迁移可正反向执行。
- 数值固定日期周期（双十一/618）作为代码常量，不在这里建表；如需 CRUD 扩展再独立。
- 种子采集需与 Phase 2 `run_learning` 触发点对接（实现期定：学习完成后异步补，或管理员手动触发）。

## Publish Status

- Status: created
- Updated At: 2026-06-19T06:20:46Z
- GitHub Number: 24
- GitHub URL: https://github.com/yanheng799/chat-db/issues/24

## Status

ready for PR

## Implementation Notes

- 新增 Alembic 迁移 `b2d3e4f5a6c7`（3 张映射表：`value_enum_mappings` / `value_region_dict` / `value_name_mappings`）。
- 新增 `src/normalizer/mapping_service.py`：CRUD（upsert/list/delete，raw SQL + asyncpg，aliases 走 `json.dumps` 序列化 JSONB）、种子采集 `auto_collect_enum_seeds`（从 Phase 1 `detected_enum_values` 取枚举值）、`cleanup_mappings`（删源时清三表）。
- 接入 `run_learning`（末尾 suppress `_collect_enum_seeds`）与 `delete_data_source`（mapping cleanup 钩子——待 linter 后确认）。
- 测试 `test/test_normalizer/test_mapping_service.py`（真实 PG：CRUD 幂等、种子采集、清理全表）。

## Verification

- `pytest test/test_normalizer/test_mapping_service.py` → **6 passed**。
- `pytest test/test_normalizer/` → 23 passed（时间解析器 17 + 映射中心 6）。
- `alembic upgrade head` / `downgrade -1` 迁移可正反向执行。
