"""FastAPI Gateway — unified REST/SSE endpoints for Phase 5-8 capabilities. (Phase 9)"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from memory.session import SessionManager

# Log through uvicorn's configured logger so INFO lines actually surface in the
# console (uvicorn's default config only wires `uvicorn*` loggers to a handler).
logger = logging.getLogger("uvicorn.error")

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


def _preview(text: object, limit: int = 200) -> str:
    """One-line, length-capped preview for log lines."""
    if text is None:
        return ""
    one_line = " ".join(str(text).split())
    return one_line if len(one_line) <= limit else one_line[:limit] + "…"


def _summarize_result(result: dict) -> str:
    """Compact outcome label for a pipeline result dict."""
    if result.get("error"):
        return f"ERROR: {_preview(result['error'], 160)}"
    res = result.get("result")
    if isinstance(res, dict) and res.get("rows") is not None:
        return f"RESULT {len(res.get('rows', []))}rows×{len(res.get('columns', []))}cols"
    if result.get("need_confirm_items"):
        return f"NEED_CONFIRM({len(result['need_confirm_items'])})"
    if result.get("sql"):
        return "DRY-RUN"
    return "EMPTY"


def _event_type(event: str | None) -> str:
    """Extract SSE event type for logging (doesn't parse full JSON)."""
    if event is None:
        return "<sentinel>"
    try:
        return json.loads(event.removeprefix("data: ")).get("type", "?")
    except Exception:
        return "?"


# ── POST /api/query ────────────────────────────────────────


@router.post("/query")
async def query(req: QueryRequest, x_session_id: str | None = Header(None)):
    sid = x_session_id or _session_mgr.create_session()
    qid = str(uuid.uuid4())
    _session_list.add(sid)
    _query_store[qid] = {"text": req.text, "session_id": sid, "status": "running"}
    logger.info("[%s] POST /api/query received sid=%s", qid, sid)

    async def generate() -> AsyncGenerator[str, None]:
        t0 = time.monotonic()
        result: dict = {}
        logger.info("[%s] query start sid=%s text=%r", qid, sid, _preview(req.text, 120))

        # ── Streaming pipeline progress via deque + Event ─────
        # The pipeline runs in a background task. Progress events are pushed
        # into a deque and signalled with an asyncio.Event. The generator
        # loop drains the deque immediately and then waits for more events
        # (or a 5s keep-alive poll), so the SSE stream stays warm and the
        # frontend idle-timeout timer is reset by every event.
        import collections

        _buf: collections.deque[str] = collections.deque()
        _buf_ready = asyncio.Event()
        _pipeline_done = asyncio.Event()

        def _emit(phase: str, message: str) -> None:
            event = _sse_event("status", {"message": message, "phase": phase})
            logger.info("[%s] sse: queuing event phase=%r message=%r", qid, phase, message)
            _buf.append(event)
            _buf_ready.set()

        def _emit_raw(event: str) -> None:
            _buf.append(event)
            _buf_ready.set()

        # Queue the first heartbeat
        _emit_raw(_sse_event("status", {"message": "starting", "session_id": sid, "query_id": qid}))
        logger.info("[%s] sse: initial 'starting' event queued", qid)

        async def _run_pipeline() -> None:
            """Run the full pipeline in a background task, feeding events
            into the shared deque."""
            nonlocal result
            logger.info("[%s] sse: _run_pipeline task started", qid)
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

                async for db_session in _db_session_factory():
                    ds_result = await db_session.execute(
                        select(DataSource).where(DataSource.is_active.is_(True)).limit(1)
                    )
                    active_ds = ds_result.scalar_one_or_none()
                    ds_id = str(active_ds.id) if active_ds else sid
                    if active_ds:
                        logger.info("[%s] active datasource id=%s engine=%s %s@%s:%s/%s",
                                    qid, ds_id, active_ds.engine, active_ds.username,
                                    active_ds.host, active_ds.port, active_ds.database)
                    else:
                        logger.warning("[%s] no active datasource", qid)

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
                            logger.info("[%s] schema loaded: %d tables", qid, len(table_rows))
                        except Exception as e:
                            logger.warning("[%s] schema load failed: %s", qid, e)

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

                    async def _vector_search(text: str, _ds_id: str) -> list[dict]:
                        _tvs = time.monotonic()
                        logger.info("[%s] vector search start (embed query → Milvus)", qid)
                        try:
                            results = await search_fields(text, uuid.UUID(_ds_id),
                                embedding_client=EmbeddingClient(settings),
                                vector_store=VectorStore(settings), top_k=5)
                            logger.info("[%s] vector search done: %d fields in %dms",
                                        qid, len(results), int((time.monotonic() - _tvs) * 1000))
                            return results
                        except Exception as e:
                            logger.warning("[%s] vector search FAILED in %dms: %r",
                                           qid, int((time.monotonic() - _tvs) * 1000), e)
                            return []

                    _target_mgr = _ConnMgr()

                    async def _query_executor(sql: str, timeout_s: float = 30.0) -> dict:
                        try:
                            engine = _target_mgr.get_or_create(ds_id, ds_config)
                            async with engine.connect() as conn:
                                from datetime import datetime as _dt, date as _d
                                start = time.monotonic()
                                logger.info("[%s] exec SQL: %s", qid, _preview(sql))
                                r = await conn.exec_driver_sql(sql)
                                rows_raw = r.fetchall()
                                cols = list(r.keys())
                                rows = []
                                for row in rows_raw:
                                    clean = tuple(
                                        v.isoformat() if isinstance(v, (_dt, _d)) else v
                                        for v in row
                                    )
                                    rows.append(clean)
                                elapsed_ms = int((time.monotonic() - start) * 1000)
                                logger.info("[%s] exec done: %d rows × %d cols in %dms",
                                            qid, len(rows), len(cols), elapsed_ms)
                                return {"columns": cols, "rows": rows, "execution_time_ms": elapsed_ms}
                        except Exception as exc:
                            logger.warning("[%s] exec failed: %s", qid, exc)
                            return {"error": str(exc), "original_sql": sql}

                    async def _on_progress(phase: str, message: str) -> None:
                        logger.info("[%s] phase=%s %s (%dms total)",
                                    qid, phase, message, int((time.monotonic() - t0) * 1000))
                        _emit(phase, message)

                    logger.info("[%s] pipeline start", qid)
                    result = await run_single_step(
                        req.text, ds_id,
                        session=db_session,
                        llm_caller=create_llm_caller(settings),
                        vector_search=_vector_search,
                        query_executor=_query_executor,
                        schema_desc=schema_desc,
                        on_progress=_on_progress,
                    )
                    logger.info("[%s] pipeline done in %dms: %s",
                                qid, int((time.monotonic() - t0) * 1000), _summarize_result(result))
                    break
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
                    _emit_raw(_sse_event("result", {"data": result["result"], "sql": result.get("sql")}))
                    _emit("", result.get("summary", "done"))
                    if have_confirm:
                        _emit_raw(_sse_event("need_confirm", {
                            "items": result["need_confirm_items"],
                            "sql": result.get("sql"),
                            "informational": True,
                        }))
                elif have_confirm:
                    _emit_raw(_sse_event("need_confirm", {
                        "items": result["need_confirm_items"],
                        "sql": result.get("sql"),
                    }))
                elif have_error:
                    _query_store[qid]["status"] = "error"
                    _query_store[qid]["error"] = result["error"]
                    _emit_raw(_sse_event("error", {"detail": result["error"], "sql": result.get("sql")}))
                else:
                    if result.get("sql"):
                        _emit_raw(_sse_event("result", {"data": result.get("result"), "sql": result.get("sql")}))
            except Exception as e:
                logger.exception("[%s] query failed after %dms", qid, int((time.monotonic() - t0) * 1000))
                _query_store[qid].update({"status": "error", "error": str(e)})
                _emit_raw(_sse_event("error", {"detail": str(e)}))
            finally:
                logger.info("[%s] sse: _run_pipeline exiting (pipeline_done set)", qid)
                _session_mgr.add_turn(sid, req.text, str(result.get("summary", "")))
                _emit_raw(_sse_event("done", {}))
                _pipeline_done.set()

        # ── Run pipeline in background, stream deque to client ──
        pipeline_task = asyncio.create_task(_run_pipeline())
        logger.info("[%s] sse: pipeline task created, entering generator loop", qid)

        while True:
            # Drain everything currently in the deque
            while _buf:
                event = _buf.popleft()
                logger.info("[%s] sse: yielding event type=%s (len=%d)",
                            qid, _event_type(event), len(event))
                yield event

            if _pipeline_done.is_set():
                logger.info("[%s] sse: pipeline done, breaking loop", qid)
                break

            # Wait for the pipeline to produce more events, with a periodic
            # keep-alive comment so the SSE stream stays warm and the frontend
            # idle-timeout timer is not triggered during long LLM calls.
            try:
                await asyncio.wait_for(_buf_ready.wait(), timeout=6.0)
            except TimeoutError:
                yield ": keepalive\n\n"
                continue
            _buf_ready.clear()

        await pipeline_task
        logger.info("[%s] query complete in %dms", qid, int((time.monotonic() - t0) * 1000))

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
