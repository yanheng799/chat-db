"""Admin management API endpoints (Phase 10)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/admin", tags=["admin"])

# ── 10.1 Sync ────────────────────────────────────────────


@router.get("/sync/status")
async def sync_status():
    return {"latest": None, "status": "no_sync_yet"}


@router.get("/sync/logs")
async def sync_logs(limit: int = 20):
    return {"logs": [], "total": 0}


@router.post("/sync/trigger")
async def sync_trigger():
    return {"task_id": "triggered", "status": "accepted"}


# ── 10.2 Graph ────────────────────────────────────────────


@router.get("/graph/nodes/{data_source_id}")
async def graph_nodes(data_source_id: str):
    return {"data_source_id": data_source_id, "nodes": []}


@router.get("/graph/edges/{data_source_id}")
async def graph_edges(data_source_id: str):
    return {"data_source_id": data_source_id, "edges": []}


# ── 10.3 Value Mappings ──────────────────────────────────


@router.get("/mappings/{mapping_type}")
async def list_mappings(mapping_type: str, data_source_id: str):
    return {"type": mapping_type, "data_source_id": data_source_id, "items": []}


class MappingItem(BaseModel):
    key: str
    value: str
    aliases: list[str] = []


@router.post("/mappings/{mapping_type}")
async def create_mapping(mapping_type: str, item: MappingItem):
    return {"created": item.key}


@router.delete("/mappings/{mapping_type}/{item_id}")
async def delete_mapping(mapping_type: str, item_id: str):
    return {"deleted": item_id}


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
