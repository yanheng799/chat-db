"""Neo4j knowledge graph store.

Builds ``Table`` / ``Column`` nodes and ``CONTAINS`` / ``REFERENCES`` /
``INFERRED_REF`` edges from application-DB metadata + Phase 2 inferred FKs.
Nodes/edges carry ``data_source_id``; the graph is **fully rebuilt** per data
source (delete that source's subgraph first, then create). V1 omits
``SAME_MEANING`` / ``JOINS_WITH`` (no data source yet).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import Settings
from metadata.models import (
    MetadataColumn,
    MetadataForeignKey,
    MetadataInferredForeignKey,
    MetadataTable,
)

logger = logging.getLogger(__name__)
_log = logging.getLogger("uvicorn.error")


def table_uid(data_source_id: str, schema: str, table: str) -> str:
    return f"{data_source_id}|{schema}.{table}"


def column_uid(data_source_id: str, schema: str, table: str, column: str) -> str:
    return f"{data_source_id}|{schema}.{table}.{column}"


class GraphStore:
    """Thin wrapper over a Neo4j database for the metadata knowledge graph."""

    def __init__(self, settings: Settings | None = None) -> None:
        from neo4j import GraphDatabase

        self._settings = settings or Settings()
        self._driver = GraphDatabase.driver(
            self._settings.neo4j_uri,
            auth=(self._settings.neo4j_user, self._settings.neo4j_password),
        )

    def close(self) -> None:
        self._driver.close()

    def _run(self, cypher: str, **params: Any) -> None:
        with self._driver.session() as session:
            session.run(cypher, **params)

    def query(self, cypher: str, **params: Any) -> list[Any]:
        """Run a read query and return the raw records (for graph_query)."""
        with self._driver.session() as session:
            return list(session.run(cypher, **params))

    def wipe_all(self) -> None:
        """Delete every node/edge (test helper; dev DB only)."""
        self._run("MATCH (n) DETACH DELETE n")

    def delete_by_data_source(self, data_source_id: uuid.UUID | str) -> None:
        ds = str(data_source_id)
        self._run("MATCH (n {data_source_id: $ds}) DETACH DELETE n", ds=ds)

    def rebuild(
        self,
        data_source_id: uuid.UUID | str,
        table_rows: list[dict[str, Any]],
        column_rows: list[dict[str, Any]],
        reference_edges: list[dict[str, Any]],
        inferred_edges: list[dict[str, Any]],
    ) -> None:
        """Full rebuild: delete the source's subgraph, then recreate nodes + edges."""
        ds = str(data_source_id)
        self.delete_by_data_source(ds)

        # Table nodes
        if table_rows:
            self._run(
                "UNWIND $rows AS r MERGE (t:Table {uid: r.uid}) "
                "SET t.data_source_id = $ds, t.schema = r.schema, t.name = r.name",
                rows=[
                    {
                        "uid": table_uid(ds, r["schema"], r["name"]),
                        "schema": r["schema"],
                        "name": r["name"],
                    }
                    for r in table_rows
                ],
                ds=ds,
            )

        # Column nodes + CONTAINS edges
        col_uids: set[str] = set()
        col_records: list[dict[str, Any]] = []
        for r in column_rows:
            uid = column_uid(ds, r["schema"], r["table"], r["name"])
            col_uids.add(uid)
            col_records.append(
                {
                    "uid": uid,
                    "table": r["table"],
                    "name": r["name"],
                    "type": r["type"],
                    "is_pk": bool(r["is_pk"]),
                    "nullable": bool(r["nullable"]),
                    "table_uid": table_uid(ds, r["schema"], r["table"]),
                }
            )
        if col_records:
            self._run(
                "UNWIND $rows AS r "
                "MERGE (col:Column {uid: r.uid}) "
                "SET col.data_source_id = $ds, col.table = r.table, col.name = r.name, "
                "col.type = r.type, col.is_pk = r.is_pk, col.nullable = r.nullable "
                "MERGE (t:Table {uid: r.table_uid}) "
                "MERGE (t)-[:CONTAINS]->(col)",
                rows=col_records,
                ds=ds,
            )

        # REFERENCES (explicit) + INFERRED_REF edges; both endpoints must exist.
        for edge_type, edges in (("REFERENCES", reference_edges), ("INFERRED_REF", inferred_edges)):
            valid = [e for e in edges if e["src_uid"] in col_uids and e["tgt_uid"] in col_uids]
            if not valid:
                continue
            self._run(
                "UNWIND $rows AS r "
                "MERGE (src:Column {uid: r.src_uid}) "
                "MERGE (tgt:Column {uid: r.tgt_uid}) "
                f"MERGE (src)-[:{edge_type} {{confidence: r.confidence}}]->(tgt)",
                rows=valid,
            )

    def count_nodes(self, data_source_id: uuid.UUID | str, label: str | None = None) -> int:
        ds = str(data_source_id)
        match = f"MATCH (n:{label} {{data_source_id: $ds}})" if label else "MATCH (n {data_source_id: $ds})"
        with self._driver.session() as session:
            return session.run(f"{match} RETURN count(n) AS c", ds=ds).single()["c"]

    def count_edges(self, data_source_id: uuid.UUID | str, edge_type: str) -> int:
        ds = str(data_source_id)
        with self._driver.session() as session:
            return session.run(
                f"MATCH ({{data_source_id: $ds}})-[r:{edge_type}]->({{data_source_id: $ds}}) RETURN count(r) AS c",
                ds=ds,
            ).single()["c"]


async def build_graph(
    session: AsyncSession,
    data_source_id: uuid.UUID,
    *,
    graph_store: GraphStore,
) -> None:
    """Read metadata + inferred FKs and rebuild the knowledge graph for a data source."""
    ds = str(data_source_id)

    tables_result = await session.execute(select(MetadataTable).where(MetadataTable.data_source_id == data_source_id))
    tables = tables_result.scalars().all()
    table_by_id = {t.id: t for t in tables}
    table_rows = [{"schema": t.schema_name, "name": t.table_name} for t in tables]

    cols_result = await session.execute(
        select(MetadataColumn).where(MetadataColumn.table_id.in_([t.id for t in tables]))
    )
    column_rows = [
        {
            "schema": table_by_id[c.table_id].schema_name,
            "table": table_by_id[c.table_id].table_name,
            "name": c.column_name,
            "type": c.data_type,
            "is_pk": c.is_primary_key,
            "nullable": c.is_nullable,
        }
        for c in cols_result.scalars().all()
    ]
    col_uids = {column_uid(ds, r["schema"], r["table"], r["name"]) for r in column_rows}

    # Explicit FKs
    fk_result = await session.execute(
        select(MetadataForeignKey)
        .join(MetadataTable, MetadataForeignKey.table_id == MetadataTable.id)
        .where(MetadataTable.data_source_id == data_source_id)
    )
    reference_edges: list[dict[str, Any]] = []
    for fk in fk_result.scalars().all():
        src_table = table_by_id.get(fk.table_id)
        if src_table is None or not fk.target_column:
            continue
        src_uid = column_uid(ds, src_table.schema_name, src_table.table_name, fk.column_name)
        tgt_uid = column_uid(ds, fk.target_schema, fk.target_table, fk.target_column)
        if src_uid in col_uids and tgt_uid in col_uids:
            reference_edges.append({"src_uid": src_uid, "tgt_uid": tgt_uid, "confidence": 1.0})

    # Inferred FKs
    inferred_result = await session.execute(
        select(MetadataInferredForeignKey).where(MetadataInferredForeignKey.data_source_id == data_source_id)
    )
    inferred_edges: list[dict[str, Any]] = []
    for ifk in inferred_result.scalars().all():
        src_uid = column_uid(ds, ifk.source_schema, ifk.source_table, ifk.source_column)
        tgt_uid = column_uid(ds, ifk.target_schema, ifk.target_table, ifk.target_column)
        if src_uid in col_uids and tgt_uid in col_uids:
            inferred_edges.append({"src_uid": src_uid, "tgt_uid": tgt_uid, "confidence": float(ifk.confidence)})

    _log.info("knowledge: graph build ds=%s tables=%d columns=%d ref_edges=%d inferred_edges=%d",
              ds, len(table_rows), len(column_rows), len(reference_edges), len(inferred_edges))
    graph_store.rebuild(data_source_id, table_rows, column_rows, reference_edges, inferred_edges)
    _log.info("knowledge: graph build done ds=%s", ds)
