"""Long-term conversation summarizer — async LLM summary → PG. (issue #47)"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def summarize_session(
    session: AsyncSession,
    session_id: str,
    turns: list[dict[str, str]],
    *,
    llm_caller: Any,
) -> None:
    if not turns:
        return
    system = "Summarize the following conversation in one Chinese sentence. Key info: tables queried, time conditions, business preferences."
    user = "Conversation:\n" + "\n".join(f"Q: {t['user']}\nA: {t['assistant']}" for t in turns)
    try:
        summary = await llm_caller(system, user)
        await session.execute(
            text("INSERT INTO conversation_summaries (id, session_id, summary, created_at) VALUES (:id, :sid, :s, :now)"),
            {"id": uuid.uuid4(), "sid": session_id, "s": summary, "now": datetime.now()},
        )
        await session.commit()
    except Exception as e:
        logger.warning("session summary failed: %s", e)
