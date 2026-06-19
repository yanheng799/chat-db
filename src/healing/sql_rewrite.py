"""SQL rewrite self-healing — LLM-based multi-strategy repair. (issue #42)"""

from __future__ import annotations

import logging
from typing import Any

from sql.security import validate_sql

logger = logging.getLogger(__name__)

_MAX_REWRITE_ATTEMPTS = 3


async def heal_sql(
    original_sql: str,
    error_message: str,
    error_type: str,
    *,
    llm_caller: Any,
    max_attempts: int = _MAX_REWRITE_ATTEMPTS,
) -> str | None:
    """Try to repair *original_sql* via LLM rewrite. Returns repaired SQL or None."""
    for attempt in range(1, max_attempts + 1):
        system = (
            "You are a SQL repair assistant. Given a failed SQL statement and the database error message, "
            "generate a corrected SQL statement. Only return the SQL itself, no explanation."
        )
        user = (
            f"Original SQL: {original_sql}\n"
            f"Error: {error_message}\n"
            f"Error type: {error_type}\n"
            f"Attempt {attempt}/{max_attempts}. "
            f"Fix the issue and return only the corrected SQL statement."
        )
        try:
            response = await llm_caller(system, user)
            sql = _extract_sql(response)
            if sql and validate_sql(sql)["passed"]:
                return sql
            logger.info("SQL rewrite attempt %d: validation failed", attempt)
        except Exception as e:
            logger.warning("SQL rewrite attempt %d failed: %s", attempt, e)
    return None


def _extract_sql(text: str) -> str | None:
    import re
    text = re.sub(r"^```(?:sql)?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text.strip())
    m = re.search(r"(?i)\bSELECT\b.+", text, re.DOTALL)
    return m.group(0).rstrip(";").strip() if m else None
