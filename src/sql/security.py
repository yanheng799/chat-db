"""SQL security validator — blacklist / whitelist / syntax + LLM regen trigger. (issue #33)"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_BLACKLIST = re.compile(
    r"(?i)\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|EXEC|INTO\s+OUTFILE|LOAD\s+DATA|SLEEP|BENCHMARK|@@)\b"
)
_WHITELIST_LIMIT = 1000


def validate_sql(sql: str) -> dict:
    """Run blacklist, whitelist, and syntax checks. Returns {passed, reason?}."""
    # Blacklist
    bl = _BLACKLIST.search(sql)
    if bl:
        return {"passed": False, "reason": f"blacklist: forbidden token '{bl.group()}'"}

    # Whitelist: must have LIMIT clause with value <= 1000
    lim = re.search(r"(?i)\bLIMIT\s+(\d+)", sql)
    if not lim:
        return {"passed": False, "reason": "whitelist: missing LIMIT clause"}
    if int(lim.group(1)) > _WHITELIST_LIMIT:
        return {"passed": False, "reason": f"whitelist: LIMIT {lim.group(1)} > {_WHITELIST_LIMIT}"}

    # Whitelist: no SELECT *
    if re.search(r"(?i)SELECT\s+\*", sql):
        return {"passed": False, "reason": "whitelist: SELECT * forbidden"}

    # Syntax check
    try:
        import sqlparse
        parsed = sqlparse.parse(sql)
        if not parsed:
            return {"passed": False, "reason": "syntax: cannot parse SQL"}
    except ImportError:
        pass  # sqlparse unavailable → skip syntax check, not a blocker
    except Exception:
        return {"passed": False, "reason": "syntax: parse error"}

    # Single-step constraint: block multi-table FROM
    tables = re.findall(r"(?i)\bJOIN\b", sql)
    from_count = len(re.findall(r"(?i)\bFROM\b", sql))
    if tables or from_count > 1:
        return {"passed": False, "reason": "single_step: multi-table query blocked (V1 only supports single-table queries)"}

    return {"passed": True}
