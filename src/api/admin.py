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
    ds_result = await session.execute(text("SELECT id FROM data_sources WHERE is_active = true LIMIT 1"))
    active = ds_result.scalar_one_or_none()
    if active is None:
        raise HTTPException(status_code=400, detail="No active data source to sync.")
    import asyncio
    from api.datasources import _run_metadata_extraction

    ds_id = active[0] if isinstance(active, tuple) else active
    asyncio.create_task(_run_metadata_extraction(ds_id, {}))
    return {"task_id": str(uuid.uuid4()), "status": "accepted", "data_source_id": str(ds_id)}


# ── 10.2 Graph ────────────────────────────────────────────


@router.get("/graph/nodes/{data_source_id}")
async def graph_nodes(data_source_id: str):
    from knowledge.graph_store import GraphStore

    store = GraphStore()
    try:
        tables = store.count_nodes(data_source_id, "Table")
        columns = store.count_nodes(data_source_id, "Column")
        return {"data_source_id": data_source_id, "tables": tables, "columns": columns}
    finally:
        store.close()


@router.get("/graph/edges/{data_source_id}")
async def graph_edges(data_source_id: str):
    from knowledge.graph_store import GraphStore

    store = GraphStore()
    try:
        return {
            "data_source_id": data_source_id,
            "edges": {
                "CONTAINS": store.count_edges(data_source_id, "CONTAINS"),
                "REFERENCES": store.count_edges(data_source_id, "REFERENCES"),
                "INFERRED_REF": store.count_edges(data_source_id, "INFERRED_REF"),
            },
        }
    finally:
        store.close()


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


# ── 10.5 Fixed Periods ───────────────────────────────────


@router.get("/fixed-periods")
async def list_fixed_periods():
    from normalizer.time_parser import FIXED_DATE_PERIODS
    return {"items": [{"name": k, "start": v[0], "end": v[1]} for k, v in FIXED_DATE_PERIODS.items()]}


# ── 10.6 Audit Policy ────────────────────────────────────

_AUDIT_POLICY = {"mode": "none", "sensitive_tables": [], "data_threshold": 1000, "complexity_threshold": 1}


@router.get("/audit-policy")
async def get_audit_policy():
    return _AUDIT_POLICY


@router.put("/audit-policy")
async def update_audit_policy(policy: dict):
    _AUDIT_POLICY.update(policy)
    return _AUDIT_POLICY
