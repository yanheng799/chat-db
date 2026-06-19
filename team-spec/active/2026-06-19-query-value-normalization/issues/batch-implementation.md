# 批量实现报告 — 查询值标准化（Phase 4）

- **slug**：`2026-06-19-query-value-normalization`
- **执行日期**：2026-06-19
- **批量范围**：6 个 AFK issue（GitHub #23–#28），分两批执行：#23/#24/#28 → #25/#26/#27
- **结果**：6/6 完成，均 `ready for PR`

## 本批队列与执行顺序

| 顺序 | Issue | GitHub | 标题 | 状态 |
|---|---|---|---|---|
| 1 | 001 | #23 | NormalizedValue + 时间解析器 | ✅ |
| 2 | 002 | #24 | 值映射中心 CRUD（迁移 + 服务 + 种子） | ✅ |
| 3 | 006 | #28 | 模糊量词检测 | ✅ |
| 4 | 003 | #25 | 枚举标准化器（5 策略 + LLM 兜底） | ✅ |
| 5 | 004 | #26 | 区域标准化器（粒度自适应 + 层级展开） | ✅ |
| 6 | 005 | #27 | 名称标准化器（7 策略 + LIKE 回退） | ✅ |

## 跳过 / 阻塞

无。所有 6 个 AFK，无 HITL。

## 关键验证命令

```
pytest test/test_normalizer/ → 47 passed (17 time + 6 mapping + 9 quantifier + 6 enum + 4 region + 5 name)
ruff check src/normalizer/ test/test_normalizer/ → clean (需 --fix)
alembic upgrade head (b2d3e4f5a6c7) → 3 迁移表 OK
```

## 主要变更

- `src/normalizer/`（新包）：`types.py` (NormalizedValue)、`time_parser.py`、`mapping_service.py`、`enum_matcher.py`、`region_parser.py`、`name_matcher.py`、`quantifier.py`。
- 迁移 `b2d3e4f5a6c7`：3 张值映射表。
- 接线：`run_learning` 追加 enum-seed call；`delete_data_source` 追加 mapping cleanup。
- `test/test_normalizer/`：conftest + 5 个测试文件。

## 未提交变更

所有变更在 `main`（未提交）。未执行 `git commit`/`push`/PR。
