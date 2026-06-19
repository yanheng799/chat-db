# 修复 sync/trigger 和 graph 端点——真实逻辑替代 stub

## Parent

PRD：`team-spec/active/2026-06-19-admin-api/prd/prd.md`（实现缺口审计）

## What to build

两个端点当前是半 stub：

1. `POST /api/admin/sync/trigger`：调 `_run_metadata_extraction` 时传入空 `{}` 作为 `ds_config`——缺少正确的连接配置（需要解密密码、构造 engine/host/port/database）。应复用 `activate_data_source` 中的配置构造逻辑。

2. `GET /api/admin/graph/nodes|edges`：只返回**计数**（tables/columns/references 数量），不返回实际的节点/边数据用于可视化。应返回节点列表（Table name/schema、Column name/type/is_pk）和边列表（type、source、target、confidence）。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] `POST /api/admin/sync/trigger` 对激活数据源触发真实同步（复用 Phase 1 的配置构造+提取逻辑）。
- [ ] `GET /api/admin/graph/nodes/{ds}` 返回 `{tables: [{name, schema, row_count?}], columns: [{table, name, type, is_pk}]}`。
- [ ] `GET /api/admin/graph/edges/{ds}` 返回 `{edges: [{type, from_table, from_column, to_table, to_column, confidence}]}`。

## Blocked by

- None

## Publish Status

- Status: created
- Updated At: 2026-06-19T08:42:42Z
- GitHub Number: 61
- GitHub URL: https://github.com/yanheng799/chat-db/issues/61
