"""User profile ORM models + CRUD helpers. (issue #48)"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def upsert_table_preference(session: AsyncSession, session_id: str, table_name: str) -> None:
    await session.execute(
        text(
            "INSERT INTO user_table_preferences (id, session_id, table_name, query_count) "
            "VALUES (:id, :sid, :tn, 1) "
            "ON CONFLICT (session_id, table_name) DO UPDATE SET query_count = user_table_preferences.query_count + 1"
        ),
        {"id": uuid.uuid4(), "sid": session_id, "tn": table_name},
    )
    await session.commit()


async def upsert_user_profile(session: AsyncSession, session_id: str, *, skill_level: str | None = None, time_preference: str | None = None) -> None:
    await session.execute(
        text(
            "INSERT INTO user_profiles (id, session_id, skill_level, time_preference, created_at) "
            "VALUES (:id, :sid, :sl, :tp, :now) "
            "ON CONFLICT (session_id) DO UPDATE SET skill_level=COALESCE(:sl2, user_profiles.skill_level), time_preference=COALESCE(:tp2, user_profiles.time_preference)"
        ),
        {"id": uuid.uuid4(), "sid": session_id, "sl": skill_level or "beginner", "tp": time_preference or "30d", "now": datetime.now(), "sl2": skill_level, "tp2": time_preference},
    )
    await session.commit()


async def add_term_correction(session: AsyncSession, session_id: str, user_term: str, corrected_term: str) -> None:
    await session.execute(
        text("INSERT INTO user_term_mappings (id, session_id, user_term, corrected_term, created_at) VALUES (:id, :sid, :ut, :ct, :now)"),
        {"id": uuid.uuid4(), "sid": session_id, "ut": user_term, "ct": corrected_term, "now": datetime.now()},
    )
    await session.commit()
