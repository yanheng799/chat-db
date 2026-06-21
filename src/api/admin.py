"""Admin management API endpoints (Phase 10)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_session
from metadata.models import MetadataSyncLog

router = APIRouter(prefix="/api/admin", tags=["admin"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


# ── 10.1 Sync ────────────────────────────────────────────


@router.get("/sync/status")
async def sync_status(session: SessionDep):
    result = await session.execute(
        select(MetadataSyncLog).order_by(MetadataSyncLog.started_at.desc()).limit(1)
    )
    latest = result.scalar_one_or_none()
    if latest is None:
        return {"latest": None, "status": "no_sync_yet"}
    return {
        "latest": {
            "id": str(latest.id),
            "sync_type": latest.sync_type,
            "status": latest.status,
            "started_at": latest.started_at.isoformat() if latest.started_at else None,
            "finished_at": latest.finished_at.isoformat() if latest.finished_at else None,
            "tables_added": latest.tables_added,
            "tables_removed": latest.tables_removed,
            "columns_changed": latest.columns_changed,
            "error_message": latest.error_message,
        }
    }


@router.get("/sync/logs")
async def sync_logs(session: SessionDep, limit: int = Query(20, ge=1, le=200)):
    result = await session.execute(
        select(MetadataSyncLog).order_by(MetadataSyncLog.started_at.desc()).limit(limit)
    )
    logs = result.scalars().all()
    return {
        "logs": [
            {
                "id": str(log.id),
                "sync_type": log.sync_type,
                "status": log.status,
                "started_at": log.started_at.isoformat() if log.started_at else None,
                "tables_added": log.tables_added,
                "tables_removed": log.tables_removed,
                "columns_changed": log.columns_changed,
            }
            for log in logs
        ],
        "total": len(logs),
    }


@router.post("/sync/trigger")
async def sync_trigger(session: SessionDep):
    from config.data_source_model import DataSource
    ds_result = await session.execute(select(DataSource).where(DataSource.is_active.is_(True)).limit(1))
    active = ds_result.scalar_one_or_none()
    if active is None:
        raise HTTPException(status_code=400, detail="No active data source to sync.")
    from config.encryption import decrypt_value
    from config.settings import Settings
    settings = Settings()
    password = decrypt_value(active.password_encrypted, settings.encryption_key)
    ds_config = {
        "id": str(active.id), "engine": active.engine, "host": active.host,
        "port": active.port, "username": active.username, "password": password,
        "database": active.database, "schema_whitelist": active.schema_whitelist,
    }
    import asyncio
    from api.datasources import _run_metadata_extraction
    asyncio.create_task(_run_metadata_extraction(active.id, ds_config))
    return {"task_id": str(uuid.uuid4()), "status": "accepted", "data_source_id": str(active.id)}


# ── 10.2 Graph ────────────────────────────────────────────


@router.get("/graph/nodes/{data_source_id}")
async def graph_nodes(data_source_id: str):
    from knowledge.graph_store import GraphStore
    store = GraphStore()
    try:
        nodes_data = store.query(
            "MATCH (n {data_source_id: $ds}) RETURN labels(n) AS labels, n.name AS name, n.schema AS schema, n.table AS table, n.type AS type, n.is_pk AS is_pk",
            ds=str(data_source_id),
        )
        tables, columns = [], []
        for r in nodes_data:
            lbls = r.get("labels", [])
            if "Table" in lbls:
                tables.append({"name": r.get("name"), "schema": r.get("schema")})
            elif "Column" in lbls:
                columns.append({"table": r.get("table"), "name": r.get("name"), "type": r.get("type"), "is_pk": r.get("is_pk")})
        return {"data_source_id": data_source_id, "tables": tables, "columns": columns}
    finally:
        store.close()


@router.get("/graph/edges/{data_source_id}")
async def graph_edges(data_source_id: str):
    from knowledge.graph_store import GraphStore
    store = GraphStore()
    try:
        edges_data = store.query(
            "MATCH (a {data_source_id: $ds})-[r]->(b {data_source_id: $ds}) WHERE type(r) IN ['REFERENCES','INFERRED_REF','CONTAINS'] "
            "RETURN type(r) AS etype, a.name AS from_name, a.table AS from_table, b.name AS to_name, b.table AS to_table, r.confidence AS confidence",
            ds=str(data_source_id),
        )
        edges = [{"type": r.get("etype"), "from_table": r.get("from_table"), "from_column": r.get("from_name"),
                  "to_table": r.get("to_table"), "to_column": r.get("to_name"),
                  "confidence": r.get("confidence")} for r in edges_data]
        return {"data_source_id": data_source_id, "edges": edges}
    finally:
        store.close()


@router.get("/graph/reachable/{data_source_id}")
async def graph_reachable(
    data_source_id: str,
    from_: str = Query(..., alias="from"),
    min_confidence: float | None = Query(None, ge=0.0, le=1.0),
):
    """Return all tables reachable from *from_* via FK edges (recursive traversal)."""
    from knowledge.graph_query import connected_subgraph
    from knowledge.graph_store import GraphStore

    store = GraphStore()
    try:
        result = await connected_subgraph(
            store, data_source_id, [from_], min_confidence=min_confidence,
        )
    finally:
        store.close()

    # Flatten: one entry per reachable table with its FK steps
    reachable: list[dict[str, Any]] = []
    for path in result.get("connected", []):
        if not path:
            continue
        reachable.append({"name": path[0]["to_table"], "path": path})

    return {
        "data_source_id": data_source_id,
        "from_table": from_,
        "tables": reachable,
    }


# ── 10.3 Value Mappings ──────────────────────────────────


@router.get("/mappings/{mapping_type}")
async def list_mappings(mapping_type: str, data_source_id: str, session: SessionDep):
    ds = uuid.UUID(data_source_id)
    if mapping_type == "enum":
        from normalizer.mapping_service import list_enum_aliases
        items = await list_enum_aliases(session, ds)
    elif mapping_type == "region":
        from normalizer.mapping_service import list_regions
        items = await list_regions(session, ds)
    elif mapping_type == "name":
        from normalizer.mapping_service import list_name_mappings
        items = await list_name_mappings(session, ds)
    else:
        raise HTTPException(400, f"Unknown mapping_type: {mapping_type}")
    return {"type": mapping_type, "data_source_id": data_source_id, "items": items}


class MappingCreate(BaseModel):
    data_source_id: str
    # enum fields
    table_name: str | None = None
    column_name: str | None = None
    value: str | None = None
    display: str | None = None
    # region fields
    code: str | None = None
    parent_code: str | None = None
    level: str | None = None
    name: str | None = None
    # name fields
    short_name: str | None = None
    full_name: str | None = None
    target_table: str | None = None
    # common
    aliases: list[str] = []


@router.post("/mappings/{mapping_type}")
async def create_mapping(mapping_type: str, item: MappingCreate, session: SessionDep):
    ds = uuid.UUID(item.data_source_id)
    if mapping_type == "enum":
        from normalizer.mapping_service import upsert_enum_alias
        await upsert_enum_alias(session, ds, item.table_name or "", item.column_name or "", item.value or "",
                                display=item.display, aliases=item.aliases)
    elif mapping_type == "region":
        from normalizer.mapping_service import upsert_region
        await upsert_region(session, ds, code=item.code or "", parent_code=item.parent_code,
                            level=item.level or "city", name=item.name or "", aliases=item.aliases)
    elif mapping_type == "name":
        from normalizer.mapping_service import upsert_name_mapping
        await upsert_name_mapping(session, ds, short_name=item.short_name or "", full_name=item.full_name or "",
                                  target_table=item.target_table, aliases=item.aliases)
    else:
        raise HTTPException(400, f"Unknown mapping_type: {mapping_type}")
    return {"created": True}


@router.delete("/mappings/{mapping_type}/{item_id}")
async def delete_mapping(mapping_type: str, item_id: str, session: SessionDep):
    mid = uuid.UUID(item_id)
    if mapping_type == "enum":
        from normalizer.mapping_service import delete_enum_alias
        ok = await delete_enum_alias(session, mid)
    else:
        await session.execute(text(f"DELETE FROM value_{mapping_type}_dict WHERE id=:id"), {"id": mid})
        await session.execute(text(f"DELETE FROM value_{mapping_type}_mappings WHERE id=:id"), {"id": mid})
        await session.commit()
        ok = True
    return {"deleted": bool(ok)}


# ── 10.4 Hot Words ───────────────────────────────────────


@router.get("/hotwords")
async def list_hotwords():
    from semantic.hot_words import HOT_WORDS
    return {"items": [{"term": k, **v} for k, v in HOT_WORDS.items()]}


class HotWordCreate(BaseModel):
    term: str
    target_table: str
    target_column: str | None = None
    formula: str | None = None
    locked: bool = False
    description: str = ""


@router.post("/hotwords")
async def create_hotword(item: HotWordCreate):
    from semantic.hot_words import HOT_WORDS
    HOT_WORDS[item.term] = {"target_table": item.target_table,
                            "target_column": item.target_column, "formula": item.formula,
                            "locked": item.locked, "description": item.description}
    return {"created": item.term}


@router.delete("/hotwords/{term}")
async def delete_hotword(term: str):
    from semantic.hot_words import HOT_WORDS
    if term in HOT_WORDS:
        del HOT_WORDS[term]
    return {"deleted": term}


# ── 10.5 Fixed Periods ───────────────────────────────────


@router.get("/fixed-periods")
async def list_fixed_periods():
    from normalizer.time_parser import FIXED_DATE_PERIODS
    return {"items": [{"name": k, "start": v[0], "end": v[1]} for k, v in FIXED_DATE_PERIODS.items()]}


class PeriodCreate(BaseModel):
    name: str
    start_mmdd: str
    end_mmdd: str


@router.post("/fixed-periods")
async def create_period(item: PeriodCreate):
    from normalizer.time_parser import FIXED_DATE_PERIODS
    FIXED_DATE_PERIODS[item.name] = (item.start_mmdd, item.end_mmdd)
    return {"created": item.name}


@router.delete("/fixed-periods/{name}")
async def delete_period(name: str):
    from normalizer.time_parser import FIXED_DATE_PERIODS
    if name in FIXED_DATE_PERIODS:
        del FIXED_DATE_PERIODS[name]
    return {"deleted": name}


# ── 10.6 Audit Policy ────────────────────────────────────

_AUDIT_POLICY = {"mode": "none", "sensitive_tables": [], "data_threshold": 1000, "complexity_threshold": 1}


@router.get("/audit-policy")
async def get_audit_policy():
    return _AUDIT_POLICY


@router.put("/audit-policy")
async def update_audit_policy(policy: dict):
    _AUDIT_POLICY.update(policy)
    return _AUDIT_POLICY
