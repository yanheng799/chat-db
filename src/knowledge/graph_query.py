"""Neo4j graph queries — shortest JOIN path + related tables (issue #20 / 003).

All queries are scoped to a single ``data_source_id``; the table/column name
matches in Cypher are always paired with ``data_source_id`` so two data sources
never get connected. V1 traverses only ``CONTAINS`` / ``REFERENCES`` /
``INFERRED_REF`` (no ``SAME_MEANING`` / ``JOINS_WITH``).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from knowledge.graph_store import GraphStore

logger = logging.getLogger(__name__)

_MAX_PATH_DEPTH = 6


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
