# 实现审核策略配置管理端点

## Parent

PRD：`team-spec/active/2026-06-19-admin-api/prd/prd.md`（10.6）

## What to build

`GET/PUT /api/admin/audit-policy` —— 查询和更新审核策略配置：敏感表列表、数据量阈值、复杂度阈值、审核模式（none/high_risk/all）。V1 存为 JSON 配置文件或 PG 单行配置表。

## Type

AFK

## Acceptance criteria

- [ ] GET 返回当前审核策略。
- [ ] PUT 更新策略配置。
- [ ] 配置持久化（重启不丢失）。

## Blocked by

- None

## Publish Status

- Status: created
- Updated At: 2026-06-19T08:27:17Z
- GitHub Number: 57
- GitHub URL: https://github.com/yanheng799/chat-db/issues/57
