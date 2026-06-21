# 数据源详情页知识图谱卡片增加递归展开起始表交互

## Parent

`team-spec/active/2026-06-19-knowledge-base/prd/prd.md` — Scenario A frontend interaction.

## What to build

Add a "select a starting table → view its reachable network" interaction to the datasource detail page's knowledge graph card. The card already shows table nodes and FK edges; this adds a dropdown to pick a starting table and a recursive tree view of its reachable network.

The interaction:
1. A `<Select>` dropdown inside the "知识图谱" card lists all tables from the already-loaded `nodes` array.
2. When the user picks a table, call `GET /api/admin/graph/reachable/{ds}?from={table}`.
3. On success, render a collapsible tree showing each reachable table with its full path from the starting table. Each path step shows: `from_table.from_column → to_table.to_column` with relation type badge (外键/推断) and confidence percentage.
4. Loading state, empty state ("该表无可达网络"), error/timeout state.
5. The entire "reachable network" section is nested inside the existing collapsible graph card, default collapsed.

## Type

HITL（需要前端产品审核交互设计）

## Acceptance criteria

- [ ] User can select a table from the nodes dropdown and trigger a reachability query.
- [ ] On success, a recursive tree shows all reachable tables with full path chains (e.g., `orders → customers → regions → countries`).
- [ ] Each path step displays via-column names, relation type (外键/推断), and confidence.
- [ ] Loading skeleton shown while API is in flight; "该表无可达网络" shown when API returns empty.
- [ ] Error/timeout state: user-visible message with retry option.
- [ ] The reachable-network section is default-collapsed inside the existing graph card.

## Blocked by

- 005-recursive-fk-traversal-api.md

## Notes

- Reuse existing `api.get()` and the `Select` component from `@/components/ui`.
- The `nodes` array is already loaded in `loadGraph()` — use it as the dropdown data source.
- Tree rendering: start simple (flat list of paths). Collapsible nested tree can be a follow-up enhancement.

## Implementation Status

- **Status**: implemented
- **Files**: `frontend/app/datasources/[id]/page.tsx` (+reachable explorer state, loadReachable, Select dropdown + expandable path cards)
- **Tests**: TypeScript clean, 349 Python tests pass
- **Verified**: 2026-06-21

## Publish Status

- Status: created
- Updated At: 2026-06-21T09:54:48Z
- GitHub Number: 66
- GitHub URL: https://github.com/yanheng799/chat-db/issues/66
