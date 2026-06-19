"""FastAPI Gateway — unified REST/SSE endpoints for Phase 5-8 capabilities. (Phase 9)"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

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
    return f"data: {json.dumps({'type': event_type, **data}, ensure_ascii=False)}\n\n"


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
            from pipeline.single_step import run_single_step
            result = await run_single_step(req.text, sid)
            _query_store[qid].update({"status": "done", "result": result.get("result"),
                                       "summary": result.get("summary", ""),
                                       "need_confirm_items": result.get("need_confirm_items", [])})
            if result.get("need_confirm_items"):
                yield _sse_event("need_confirm", {"items": result["need_confirm_items"]})
            elif result.get("error"):
                _query_store[qid]["status"] = "error"
                _query_store[qid]["error"] = result["error"]
                yield _sse_event("error", {"detail": result["error"]})
            else:
                yield _sse_event("result", {"data": result.get("result")})
                yield _sse_event("status", {"message": result.get("summary", "done")})
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
