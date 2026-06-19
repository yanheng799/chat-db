# 管理端 API（Phase 10）— 规格细化

- **slug**：`2026-06-19-admin-api`
- **状态**：refining 完成（1 轮，行为由 dev plan 充分指定，直接进入 review）
- **基线**：dev plan Phase 10

## 需求复述

统一管理端后端 API——同步状态查看、图谱数据导出、值映射 CRUD、热词词典管理、审核策略配置、固定日期周期管理。前端 UI 统一延 Phase 10.b。

## 范围内

| 子领域 | 端点 |
|--------|------|
| 10.1 同步状态 | `GET /api/admin/sync/status`, `GET /api/admin/sync/logs`, `POST /api/admin/sync/trigger` |
| 10.2 图谱数据 | `GET /api/admin/graph/nodes/{ds}`, `GET /api/admin/graph/edges/{ds}` |
| 10.3 值映射 | CRUD `/api/admin/mappings/enum|region|name` |
| 10.4 热词词典 | CRUD `/api/admin/hotwords` |
| 10.5 固定日期 | CRUD `/api/admin/fixed-periods` |
| 10.6 审核策略 | CRUD `/api/admin/audit-policy` |

## 范围外

- 管理端前端 UI（Phase 10.b）
- 认证鉴权（Phase 9+）

## Change Log

- 2026-06-19（第 1 轮）：确认范围 = 方案 A（管理端 API only；前端延 Phase 10.b）。