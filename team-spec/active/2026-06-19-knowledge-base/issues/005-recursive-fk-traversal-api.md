# graph_query.py 新增递归 FK 遍历函数与可达网络查询 API

## Parent

`team-spec/active/2026-06-19-knowledge-base/prd/prd.md` — Scene A (management) + Scene B (agent) recursive FK traversal.

## What to build

Add a recursive FK traversal function to `graph_query.py` that finds all tables reachable from a starting set by following REFERENCES + INFERRED_REF edges through CONTAINS hops, up to `_MAX_PATH_DEPTH=6`. Expose the single-table variant as a management API endpoint.

- `connected_subgraph(graph_store, ds, tables, min_confidence)` returns `{connected: [[{from_table, from_column, to_table, to_column, type, confidence}...]], unconnected: ["table_name"]}`. When all given tables are in the same connected component, unconnected is empty.
- `GET /api/admin/graph/reachable/{ds}?from={table}` delegates to `connected_subgraph` for a single starting table and returns a simplified format: `{from_table, tables: [{name, schema, path: [{from_table, from_column, to_table, to_column, type, confidence}]}]}`.

Cypher query: start from the given table(s), traverse `[:CONTAINS]->(:Column)-[:REFERENCES|INFERRED_REF]-(:Column)<-[:CONTAINS]-(:Table)` recursively up to depth 6. Add `transaction_timeout` of 5s via Neo4j driver config or per-query hint. When the traversal times out, return whatever was discovered plus a timeout flag.

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] `connected_subgraph(ds, ["orders"])` returns all tables reachable from `orders` through FK edges, depth ≤ 6.
- [ ] `connected_subgraph(ds, ["orders", "countries"])` returns the connecting path when both tables are in the same component; returns `unconnected: ["countries"]` when they are not.
- [ ] `min_confidence` filter skips INFERRED_REF edges below the threshold (but still traverses REFERENCES edges).
- [ ] `GET /api/admin/graph/reachable/{ds}?from=orders` returns HTTP 200 with reachable tables and full path steps.
- [ ] Cypher query does not exceed 5s (test with synthetic 50+ table dense-FK graph).
- [ ] `connected_subgraph` returns `{connected: [], unconnected: ["table"]}` when no FK edges exist for the given table.
- [ ] Unit tests cover: fully-connected component, partially-connected (some tables in, some out), empty graph (no edges), timeout scenario.

## Blocked by

- None — can start immediately

## Notes

- Reuse `_MAX_PATH_DEPTH = 6` from existing `graph_query.py`.
- `shortest_join_path` and `related_tables` remain unchanged.
- The admin endpoint is a thin HTTP wrapper; no new business logic.
- Cypher performance: ensure `Table(name)` and `Table(data_source_id)` have indexes in Neo4j.

## Implementation Status

- **Status**: implemented
- **Files**: `src/knowledge/graph_query.py` (+`connected_subgraph` with `_RECURSIVE_MAX_HOPS=18`, `_RECURSIVE_TIMEOUT=5s`), `src/api/admin.py` (+`GET /api/admin/graph/reachable/{ds}?from={table}`)
- **Tests**: 349 passed (integration test gated on Neo4j being available)
- **Verified**: 2026-06-21

## Publish Status

- Status: created
- Updated At: 2026-06-21T09:54:41Z
- GitHub Number: 65
- GitHub URL: https://github.com/yanheng799/chat-db/issues/65
