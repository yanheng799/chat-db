## Parent

`team-spec/active/2026-06-19-chat-db-nextjs-frontend/prd/prd.md` — Chat-DB Next.js 前端重写

## What to build

数据源详情页 `/datasources/[id]`：展示单个数据源的完整信息、元数据概览、测试连接、激活/停用、同步操作（全量/按表范围）+ 同步日志、元数据学习 + 学习日志、删除操作（含 Milvus/Neo4j 清理提示）。

具体清单：
- `app/datasources/[id]/page.tsx`：详情页主组件，顶部 「← 返回列表」按钮
- 基本信息区：名称、引擎、主机、端口、数据库、激活状态（绿/灰点）
- 元数据概览：`GET /api/datasources/{id}/metadata` → 表数 × 列数统计卡片
- 操作按钮行：[测试连接] [激活] / [停用]
- 同步操作区：
  - 「触发全量同步」按钮 → `POST /api/datasources/{id}/sync` → 按钮 disabled + "同步中…" → 每 2s 轮询 `GET /api/datasources/{id}/sync-logs` 最新一条直到 success/failed，最多 30 次
  - 「按表同步」按钮 → 弹出表选择器（填入 schema + table 名） → `POST /api/datasources/{id}/sync` { table_scope: [{schema, table}] }
  - 同步日志列表：`GET /api/datasources/{id}/sync-logs` → 最近 5 条日志（类型/状态/时间/新增/删除/变更列数）
  - 409 冲突处理：后端返回 409 "A sync is already in progress" → Toast "已有同步任务运行中"
- 学习操作区：
  - 「触发元数据学习」按钮 → `POST /api/datasources/{id}/learn` → 返回 learning_log_id
  - 学习日志列表：`GET /api/datasources/{id}/learning-logs` → 最近 5 条日志（触发类型/状态/L0/L1/L2 数量/LLM 调用次数）
- 危险操作区（红色边框）：
  - 「删除数据源」按钮 → `ConfirmDialog` 含详细清理提示"此操作将同时清理 Milvus 向量数据和 Neo4j 图数据，不可撤销" → 确认 → `DELETE /api/datasources/{id}` → 204 → `router.push('/datasources')` + Toast

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given 从数据源列表点击某数据源 [详情]，When 进入 /datasources/{id}，Then 显示基本信息（名称/引擎/host/port/db/状态）+ 元数据概览（表数/列数）
- [ ] Given 详情页，When 点击「触发全量同步」，Then 按钮变为 disabled → 每 2s 轮询 sync-logs → 成功后刷新日志列表 + Toast "同步完成"
- [ ] Given 同步正在运行，When 再次点击「触发全量同步」，Then 后端返回 409 → Toast "已有同步任务运行中"
- [ ] Given 详情页，When 点击「按表同步」→ 输入 schema + table → 提交，Then POST sync 携带 table_scope
- [ ] Given 详情页，When 点击「触发元数据学习」，Then POST learn 成功 → 显示 learning_log_id → 刷新学习日志
- [ ] Given 点击「删除数据源」→ 弹出含 Milvus/Neo4j 清理警告的确认对话框 → 确认，Then DELETE 成功 → 自动跳转到 /datasources 列表 + Toast "数据源已删除"
- [ ] Given 点击「← 返回列表」，Then 导航回 /datasources

## Blocked by

- 007（datasource-list-create-form）— 依赖列表页提供导航入口；依赖 datasources store 中的基础 actions

## Notes

- 同步轮询逻辑与 Issue 005 的 SyncStatusCard 相同，可提取共享 hook `usePolling(apiCall, { interval: 2000, maxAttempts: 30 })`
- 按表同步的表选择器：两个输入框（schema + table），可动态添加行（多张表同时同步）
- 详情页的测试连接/激活/停用逻辑可与 Issue 007 共享 `useDataSourceStore` actions
- 删除数据源后：应用 DB 中数据源记录被删（CASCADE 清理元数据表），后端 `datasources.py:138-149` 异步清理 Milvus + Neo4j
