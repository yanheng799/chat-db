# 实现错误学习闭环——healing_records 表+迁移+反馈 Phase 3

## Parent

PRD：`team-spec/active/2026-06-19-error-self-healing/prd/prd.md`（7.5 错误学习闭环）

## What to build

创建 `healing_records` 表的 Alembic 迁移（`error_type, original_sql, fix_type, fix_sql, success, timestamp`）。每次自愈尝试（无论成功失败）追加一条记录。成功修复的类型做反馈：`fix_type=metadata_sync` → 调 Phase 3 增量更新向量库/图谱（对应字段已刷新）；`fix_type=auto_join` → V1 不记频次（`JOINS_WITH` 累计延 Phase 11）。`fix_type=sql_rewrite` → 仅记录错误模式。`healing_records` V1 仅追加、不检索、不修剪。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given `alembic upgrade head` → `healing_records` 表含 `error_type, original_sql, fix_type, fix_sql, success, timestamp`。
- [ ] Given 自愈成功/失败 → 追加记录到 `healing_records`，字段完整。
- [ ] Given `fix_type=metadata_sync` + success → 调 Phase 3 刷新（增量更新向量库+图谱）。
- [ ] `healing_records` 无清理策略（V1 仅追加）。

## Blocked by

- #1（需分类器输出 error_type）

## Notes

- 反馈到 Phase 3 的调用：对 `metadata_sync` 成功修复 → 调用 Phase 3 `build_field_vectors`（增量）+ `build_graph`（全量重建），与 `run_learning` 中的知识库刷新模式一致。

## Publish Status

- Status: created
- Updated At: 2026-06-19T07:50:02Z
- GitHub Number: 44
- GitHub URL: https://github.com/yanheng799/chat-db/issues/44
