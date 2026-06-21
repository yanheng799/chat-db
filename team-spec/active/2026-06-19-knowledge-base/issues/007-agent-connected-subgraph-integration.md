# single_step.py 集成 connected_subgraph 替代逐对最短路径查询

## Parent

`team-spec/active/2026-06-19-knowledge-base/prd/prd.md` — Scenario B agent integration.

## What to build

Replace the N×N pairwise `shortest_join_path` calls in `single_step.py` with a single `connected_subgraph` call. When the pipeline detects multiple tables mentioned in a query, instead of iterating over all table pairs and calling `shortest_join_path` for each, call `connected_subgraph` once to discover the full connected subgraph. Keep `shortest_join_path` as fallback — if `connected_subgraph` fails or times out, fall back to the existing pairwise logic.

Changes:
1. In `single_step.py`, replace the section that builds `join_paths` by looping over table pairs with `shortest_join_path`.
2. Call `connected_subgraph(graph_store, ds, tables)` instead.
3. If it returns successfully with connected paths, use those as `join_paths` for SQL generation.
4. If it raises or times out, log a warning and fall back to the existing pairwise `shortest_join_path` loop (preserved).

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given a query mentioning 3 tables that are all FK-connected, `single_step.py` calls `connected_subgraph` once (not 3 choose 2 = 3 pairwise calls).
- [ ] When `connected_subgraph` succeeds, the resulting `join_paths` are passed to `generate_sql` and produce correct JOIN SQL.
- [ ] When `connected_subgraph` raises or times out, the pipeline falls back to the existing `shortest_join_path` pairwise loop with a warning log.
- [ ] Existing pipeline tests continue to pass (mock `connected_subgraph` in tests).
- [ ] `shortest_join_path` is preserved and NOT deleted.

## Blocked by

- 005-recursive-fk-traversal-api.md

## Notes

- The existing test file `test/test_semantic/test_pipeline.py` uses mock LLM + mock vector search. Add mock for `connected_subgraph` to test both success and fallback paths.
- `connected_subgraph` returns `{connected: [[path...]], unconnected: [...]}`. Only the `connected` paths are forwarded to `generate_sql` as `join_paths`. Unconnected tables should trigger a warning log (they won't be joined).

## Implementation Status

- **Status**: implemented
- **Files**: `src/pipeline/single_step.py` (replaced N×N pairwise `shortest_join_path` loop with `connected_subgraph` + fallback)
- **Tests**: 349 passed
- **Verified**: 2026-06-21

## Publish Status

- Status: created
- Updated At: 2026-06-21T09:54:56Z
- GitHub Number: 67
- GitHub URL: https://github.com/yanheng799/chat-db/issues/67
