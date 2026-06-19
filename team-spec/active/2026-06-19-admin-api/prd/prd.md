# 管理端 API（Phase 10）— 6 组管理 CRUD 端点

## 问题陈述

Phase 2-9 建了完整能力但配置全靠代码/DB 直操。管理员需要一个后端 API 来管理同步状态、图谱、值映射、热词、审核策略、固定日期——供未来的管理 UI（Phase 10.b）或脚本调用。

## 目标

- 6 组 REST CRUD 端点覆盖全部管理功能。
- 复用已有服务和模型，轻量封装。

## 端点

| 10.1 同步 | `GET /api/admin/sync/status`, `GET /logs`, `POST /trigger` |
| 10.2 图谱 | `GET /api/admin/graph/nodes/{ds}`, `GET /edges/{ds}` |
| 10.3 值映射 | CRUD `/api/admin/mappings/enum|region|name` |
| 10.4 热词 | CRUD `/api/admin/hotwords` |
| 10.5 固定日期 | CRUD `/api/admin/fixed-periods` |
| 10.6 审核策略 | CRUD `/api/admin/audit-policy` |

## 非目标

- 管理端前端 UI（Phase 10.b）
- 认证鉴权

## 实现决策

- `src/api/admin.py`（FastAPI router，`prefix=/api/admin`）。
- 复用：Phase 1 sync、Phase 3 graph、Phase 4 value mappings、Phase 5 hot words、Phase 6 audit。

## 预拆 issue

A 同步+图谱、B 值映射+热词+固定日期、C 审核策略。
