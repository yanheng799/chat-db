"""FastAPI Gateway — unified REST/SSE endpoints for Phase 5-8 capabilities. (Phase 9)"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from memory.session import SessionManager

router = APIRouter(prefix="/api", tags=["gateway"])
_session_mgr = SessionManager()
_query_store: dict[str, dict] = {}  # query_id → query detail
_session_list: set[str] = set()     # known session ids


class QueryRequest(BaseModel):
    text: str


class ConfirmRequest(BaseModel):
    confirmed: bool = True


# ── SSE helper ──────────────────────────────────────────────


def _sse_event(event_type: str, data: dict) -> str:
    return f"data: {json.dumps({'type': event_type, **data}, ensure_ascii=False, default=str)}\n\n"


# ── POST /api/query ────────────────────────────────────────


@router.post("/query")
async def query(req: QueryRequest, x_session_id: str | None = Header(None)):
    sid = x_session_id or _session_mgr.create_session()
    qid = str(uuid.uuid4())
    _session_list.add(sid)
    _query_store[qid] = {"text": req.text, "session_id": sid, "status": "running"}

    async def generate() -> AsyncGenerator[str, None]:
        yield _sse_event("status", {"message": "starting", "session_id": sid, "query_id": qid})
        try:
            from config.data_source_model import DataSource
            from config.database import get_session as _db_session_factory
            from config.settings import Settings
            from knowledge.embedding import EmbeddingClient
            from knowledge.vector_store import VectorStore, search_fields
            from llm.client import create_llm_caller
            from pipeline.single_step import run_single_step
            from metadata.models import MetadataTable, MetadataColumn
            from config.encryption import decrypt_value
            from db.connection import ConnectionManager as _ConnMgr

            settings = Settings()

            # Single session for everything: lookup active DS + schema + pipeline
            async for db_session in _db_session_factory():
                # Find active datasource
                ds_result = await db_session.execute(
                    select(DataSource).where(DataSource.is_active.is_(True)).limit(1)
                )
                active_ds = ds_result.scalar_one_or_none()
                ds_id = str(active_ds.id) if active_ds else sid

                # Build schema description
                schema_desc = ""
                if active_ds:
                    try:
                        table_rows = (await db_session.execute(
                            select(MetadataTable).where(MetadataTable.data_source_id == ds_id)
                        )).scalars().all()
                        schema_parts = []
                        for t in table_rows:
                            cols = (await db_session.execute(
                                select(MetadataColumn.column_name, MetadataColumn.data_type)
                                .where(MetadataColumn.table_id == t.id)
                                .order_by(MetadataColumn.ordinal_position)
                            )).all()
                            col_str = ", ".join(f"{c[0]} {c[1]}" for c in cols)
                            schema_parts.append(f"  {t.schema_name}.{t.table_name}({col_str})")
                        schema_desc = "Tables:\n" + "\n".join(schema_parts) if schema_parts else ""
                    except Exception:
                        pass

                # Datasource connection config
                if not active_ds:
                    result = {"error": "没有激活的数据源。请先在数据源管理中激活一个数据源。"}
                    break
                ds_config = {
                    "id": str(active_ds.id), "engine": active_ds.engine,
                    "host": active_ds.host, "port": active_ds.port,
                    "username": active_ds.username,
                    "password": decrypt_value(active_ds.password_encrypted, settings.encryption_key),
                    "database": active_ds.database,
                }

                # Vector search wrapper
                async def _vector_search(text: str, _ds_id: str) -> list[dict]:
                    try:
                        return await search_fields(text, uuid.UUID(_ds_id),
                            embedding_client=EmbeddingClient(settings),
                            vector_store=VectorStore(settings), top_k=5)
                    except Exception:
                        return []

                # Query executor (target DB)
                _target_mgr = _ConnMgr()

                async def _query_executor(sql: str, timeout_s: float = 30.0) -> dict:
                    try:
                        engine = _target_mgr.get_or_create(ds_id, ds_config)
                        async with engine.connect() as conn:
                            import time
                            from datetime import datetime as _dt, date as _d
                            start = time.monotonic()
                            r = await conn.exec_driver_sql(sql)
                            rows_raw = r.fetchall()
                            cols = list(r.keys())
                            # Convert datetime/date to ISO strings for JSON serialization
                            rows = []
                            for row in rows_raw:
                                clean = tuple(
                                    v.isoformat() if isinstance(v, (_dt, _d)) else v
                                    for v in row
                                )
                                rows.append(clean)
                            return {"columns": cols, "rows": rows,
                                    "execution_time_ms": int((time.monotonic() - start) * 1000)}
                    except Exception as exc:
                        return {"error": str(exc), "original_sql": sql}

                result = await run_single_step(
                    req.text, ds_id,
                    session=db_session,
                    llm_caller=create_llm_caller(settings),
                    vector_search=_vector_search,
                    query_executor=_query_executor,
                    schema_desc=schema_desc,
                )
                break  # one session, clean exit
            else:
                result = {"error": "No database session available"}
            _query_store[qid].update({"status": "done", "result": result.get("result"),
                                       "sql": result.get("sql"),
                                       "summary": result.get("summary", ""),
                                       "need_confirm_items": result.get("need_confirm_items", [])})
            have_confirm = bool(result.get("need_confirm_items"))
            have_result = bool(result.get("result") and result["result"] != "(dry-run: no executor)")
            have_error = bool(result.get("error"))

            if have_result:
                # Send result first (with SQL + data)
                yield _sse_event("result", {"data": result["result"], "sql": result.get("sql")})
                yield _sse_event("status", {"message": result.get("summary", "done")})
                # Then send confirm items as informational (non-blocking)
                if have_confirm:
                    yield _sse_event("need_confirm", {
                        "items": result["need_confirm_items"],
                        "sql": result.get("sql"),
                        "informational": True,
                    })
            elif have_confirm:
                # No result yet — confirm needed before execution
                yield _sse_event("need_confirm", {
                    "items": result["need_confirm_items"],
                    "sql": result.get("sql"),
                })
            elif have_error:
                _query_store[qid]["status"] = "error"
                _query_store[qid]["error"] = result["error"]
                yield _sse_event("error", {"detail": result["error"], "sql": result.get("sql")})
            else:
                # Dry-run or no result
                if result.get("sql"):
                    yield _sse_event("result", {"data": result.get("result"), "sql": result.get("sql")})
        except Exception as e:
            _query_store[qid].update({"status": "error", "error": str(e)})
            yield _sse_event("error", {"detail": str(e)})
        _session_mgr.add_turn(sid, req.text, str(result.get("summary", "")))
        yield _sse_event("done", {})

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"X-Session-Id": sid} if not x_session_id else {})


# ── GET /api/query/{id} ────────────────────────────────────


@router.get("/query/{query_id}")
async def get_query_detail(query_id: str):
    detail = _query_store.get(query_id)
    if detail is None:
        from fastapi import HTTPException
        raise HTTPException(404, "Query not found")
    return detail


# ── POST /api/session ──────────────────────────────────────


@router.post("/session")
async def create_session():
    sid = _session_mgr.create_session()
    return {"session_id": sid}


# ── GET /api/conversations (list) ───────────────────────────


@router.get("/conversations")
async def list_conversations():
    return {"sessions": [{"session_id": s} for s in sorted(_session_list)]}


# ── GET /api/conversations/{sid} ────────────────────────────


@router.get("/conversations/{session_id}")
async def get_conversations(session_id: str):
    ctx = _session_mgr.get_context(session_id)
    return {"session_id": session_id, "turns": ctx}


# ── POST /api/query/{id}/confirm & cancel ─────────────────


@router.post("/query/{query_id}/confirm")
async def confirm_query(query_id: str, req: ConfirmRequest):
    return {"query_id": query_id, "confirmed": req.confirmed, "status": "acknowledged"}


@router.post("/query/{query_id}/cancel")
async def cancel_query(query_id: str):
    return {"query_id": query_id, "status": "cancelled"}


# ── GET /api/health ────────────────────────────────────────


@router.get("/health")
async def health():
    return {"status": "ok"}
