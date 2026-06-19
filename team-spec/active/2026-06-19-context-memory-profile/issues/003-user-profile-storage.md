# 创建用户画像表+迁移+CRUD——三表+increment模式

## Parent

PRD：`team-spec/active/2026-06-19-context-memory-profile/prd/prd.md`（8.5）

## What to build

创建 3 张画像表的 Alembic 迁移：`user_profiles`（session_id PK, skill_level, time_preference）、`user_table_preferences`（session_id+table_name 唯一约束，`ON CONFLICT UPDATE query_count+1`）、`user_term_mappings`（session_id, user_term, corrected_term）。提供基本 CRUD（upsert 画像、增量表偏好、插入术语映射）。为 Phase 9 预留 `user_id` 列（NULLABLE）。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] `alembic upgrade head` → 三表创建成功，含唯一约束。
- [ ] `ON CONFLICT (session_id, table_name) DO UPDATE query_count+1` 幂等递增。
- [ ] 画像表 CRUD 可测试。
- [ ] `user_id` 列预留为 NULLABLE。

## Blocked by

- None

## Publish Status

- Status: created
- Updated At: 2026-06-19T08:09:35Z
- GitHub Number: 48
- GitHub URL: https://github.com/yanheng799/chat-db/issues/48
