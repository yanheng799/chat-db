"""Neo4j graph queries — shortest JOIN path + related tables (issue #20 / 003).

All queries are scoped to a single ``data_source_id``; the table/column name
matches in Cypher are always paired with ``data_source_id`` so two data sources
never get connected. V1 traverses only ``CONTAINS`` / ``REFERENCES`` /
``INFERRED_REF`` (no ``SAME_MEANING`` / ``JOINS_WITH``).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from knowledge.graph_store import GraphStore

logger = logging.getLogger(__name__)

_MAX_PATH_DEPTH = 6
_RECURSIVE_MAX_HOPS = 18  # ~6 FK hops (Table→Col→Col→Table = 3 pattern hops per FK)
_RECURSIVE_TIMEOUT = 5.0  # seconds


async def shortest_join_path(
    graph_store: GraphStore,
    data_source_id: uuid.UUID | str,
    table_a: str,
    table_b: str,
    *,
    min_confidence: float | None = None,
) -> list[dict[str, Any]]:
    """Return the join steps on the shortest path between two tables.

    Each step: ``{from_table, from_column, to_table, to_column, type, confidence}``.
    Empty list when no path exists or (with ``min_confidence``) the shortest path
    uses an ``INFERRED_REF`` edge below the threshold.
    """
    ds = str(data_source_id)
    params: dict[str, Any] = {"ds": ds, "ta": table_a, "tb": table_b}
    cypher = (
        "MATCH (a:Table {data_source_id: $ds, name: $ta}), "
        "(b:Table {data_source_id: $ds, name: $tb}) "
        "WHERE a <> b "
        f"MATCH path = shortestPath((a)-[:CONTAINS|REFERENCES|INFERRED_REF*..{_MAX_PATH_DEPTH}]-(b)) "
    )
    if min_confidence is not None:
        params["min"] = float(min_confidence)
        cypher += "WHERE all(r IN relationships(path) WHERE type(r) <> 'INFERRED_REF' OR r.confidence >= $min) "
    cypher += "RETURN nodes(path) AS ns, relationships(path) AS rs LIMIT 1"

    records = graph_store.query(cypher, **params)
    if not records:
        return []
    rec = records[0]
    return _path_to_join_steps(rec["ns"], rec["rs"])


async def related_tables(
    graph_store: GraphStore,
    data_source_id: uuid.UUID | str,
    table: str,
    *,
    min_confidence: float | None = None,
) -> list[dict[str, Any]]:
    """Return tables directly joinable to ``table`` (one FK edge away)."""
    ds = str(data_source_id)
    params: dict[str, Any] = {"ds": ds, "tbl": table}
    where = "WHERE ot.data_source_id = $ds AND ot.name <> $tbl"
    if min_confidence is not None:
        params["min"] = float(min_confidence)
        where += " AND (type(r) <> 'INFERRED_REF' OR r.confidence >= $min)"
    cypher = (
        "MATCH (t:Table {data_source_id: $ds, name: $tbl})-[:CONTAINS]->(c:Column) "
        "MATCH (c)-[r:REFERENCES|INFERRED_REF]-(o:Column) "
        "MATCH (ot:Table {data_source_id: $ds})-[:CONTAINS]->(o) "
        f"{where} "
        "RETURN DISTINCT ot.name AS other, c.name AS via_from, o.name AS via_to, "
        "type(r) AS etype, r.confidence AS conf "
        "ORDER BY other"
    )
    return [
        {
            "table": row["other"],
            "from_column": row["via_from"],
            "to_column": row["via_to"],
            "type": row["etype"],
            "confidence": row["conf"],
        }
        for row in graph_store.query(cypher, **params)
    ]


async def connected_subgraph(
    graph_store: GraphStore,
    data_source_id: uuid.UUID | str,
    tables: list[str],
    *,
    min_confidence: float | None = None,
) -> dict[str, Any]:
    """Find the FK-connected subgraph covering the given tables.

    Traverses ``CONTAINS`` / ``REFERENCES`` / ``INFERRED_REF`` edges
    recursively (up to :data:`_RECURSIVE_MAX_HOPS` hops) to discover all
    tables reachable from the given set.  Returns::

        {
            "connected": [
                [
                    {"from_table":..., "from_column":..., "to_table":..., "to_column":..., "type":..., "confidence":...},
                    ...
                ],
                ...
            ],
            "unconnected": ["table_name", ...]
        }

    ``connected`` contains one entry per reachable target table (the shortest
    path from the nearest source table).  ``unconnected`` lists input tables
    that have no FK path to any of the other input tables.

    The query is wrapped in :func:`asyncio.wait_for` with a 5 s timeout to
    prevent runaway traversal on large/dense graphs.
    """
    ds = str(data_source_id)
    params: dict[str, Any] = {"ds": ds}
    # Build a disjunction of start-table clauses
    tbl_param = {f"t{i}": t for i, t in enumerate(tables)}
    params.update(tbl_param)
    params["min_confidence"] = float(min_confidence) if min_confidence is not None else 0.0

    # Single-hop: find tables directly joinable from any start table via FK edges.
    # Each record gives one FK step; multiple steps to the same target table are
    # grouped into a single path entry.
    from_table = tables[0]  # primary start table
    # Edges matched undirected: the stored FK edge points source→target, so a
    # directed match misses the target table when it is the traversal start
    # (tables[] order is nondeterministic); a JOIN is valid either way. This
    # mirrors shortest_join_path above. The trailing CONTAINS is also reversed
    # in the graph (Table→Column), so it must be undirected too.
    cypher = (
        "MATCH (start:Table {data_source_id: $ds, name: $t0}) "
        "MATCH (start)-[:CONTAINS]-(c:Column)-[r:REFERENCES|INFERRED_REF]-(o:Column)-[:CONTAINS]-(other:Table) "
        "WHERE other.data_source_id = $ds AND start <> other "
        "AND (type(r) <> 'INFERRED_REF' OR r.confidence >= $min_confidence) "
        "RETURN other.name AS name, "
        "c.name AS from_col, r.confidence AS conf, "
        "o.name AS to_col, type(r) AS etype "
        "ORDER BY other.name, c.name"
    )

    try:
        async def _query() -> list[Any]:
            return graph_store.query(cypher, **params)

        records = await asyncio.wait_for(_query(), timeout=_RECURSIVE_TIMEOUT)
    except TimeoutError:
        logger.warning("connected_subgraph timed out ds=%s", ds)
        return {"connected": [], "unconnected": list(tables)}
    except Exception as exc:
        logger.warning("connected_subgraph query failed: %s", exc)
        return {"connected": [], "unconnected": list(tables)}

    if not records:
        return {"connected": [], "unconnected": list(tables)}

    # Each record is one FK step: {name, from_col, conf, to_col, etype}
    # Group by target table name into single-step paths.
    by_target: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        target = rec["name"]
        step = {
            "from_table": from_table,
            "from_column": rec["from_col"],
            "to_table": target,
            "to_column": rec["to_col"],
            "type": rec["etype"],
            "confidence": rec["conf"],
        }
        by_target.setdefault(target, []).append(step)

    connected: list[list[dict[str, Any]]] = [
        steps for steps in by_target.values()
    ]
    found_tables = set(by_target.keys())
    unconnected = [t for t in tables if t not in found_tables]
    return {"connected": connected, "unconnected": unconnected}


def _path_to_join_steps(nodes: list[Any], rels: list[Any]) -> list[dict[str, Any]]:
    """Extract FK join steps (Column→Column edges) from a Neo4j path."""
    node_by_id = {_node_id(n): n for n in nodes}
    steps: list[dict[str, Any]] = []
    for rel in rels:
        if rel.type not in ("REFERENCES", "INFERRED_REF"):
            continue
        start, end = _rel_endpoints(rel)
        src = node_by_id.get(start)
        tgt = node_by_id.get(end)
        if src is None or tgt is None:
            continue
        steps.append(
            {
                "from_table": src["table"],
                "from_column": src["name"],
                "to_table": tgt["table"],
                "to_column": tgt["name"],
                "type": rel.type,
                "confidence": rel.get("confidence"),
            }
        )
    return steps


def _node_id(node: Any) -> str:
    """Return a node's element id across neo4j-driver versions."""
    return getattr(node, "element_id", None) or str(node.id)


def _rel_endpoints(rel: Any) -> tuple[str, str]:
    """Return (start_element_id, end_element_id) of a relationship across versions."""
    nodes = getattr(rel, "nodes", None)
    if nodes and isinstance(nodes[0], str):
        return nodes[0], nodes[1]
    start = getattr(rel, "start_node", None)
    end = getattr(rel, "end_node", None)
    if start is not None and end is not None:
        return _node_id(start), _node_id(end)
    # Legacy integer-id fallback
    return str(rel.start), str(rel.end)
