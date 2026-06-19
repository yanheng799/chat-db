"""SQL executor — read-only + timeout + result capture. (issue #34)"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def execute_sql(
    session: AsyncSession,
    sql: str,
    *,
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    """Execute *sql* on the target data source via *session* (read-only, timeout).

    Returns ``{columns, rows, execution_time_ms}`` on success, or ``{error, original_sql}``.
    V1 does not retry (self-healing deferred to Phase 7).
    """
    start = time.monotonic()
    try:
        # SET TRANSACTION READ ONLY must have been applied by the connection layer.
        result = await session.execute(text(sql).execution_options(timeout=timeout_s))
        rows = result.fetchall()
        columns = list(result.keys())
        elapsed = int((time.monotonic() - start) * 1000)
        return {
            "columns": columns,
            "rows": [tuple(r) for r in rows],
            "execution_time_ms": elapsed,
        }
    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        logger.warning("SQL execute failed (%dms): %s | SQL: %s", elapsed, e, sql[:200])
        return {
            "error": str(e),
            "original_sql": sql,
            "execution_time_ms": elapsed,
        }
