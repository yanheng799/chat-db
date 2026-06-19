"""SQL error classifier — categorize DB errors for targeted self-healing. (issue #41)"""

from __future__ import annotations

import logging
import re
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorType(str, Enum):
    TABLE_NOT_FOUND = "table_not_found"
    COLUMN_NOT_FOUND = "column_not_found"
    SQL_SYNTAX_ERROR = "sql_syntax_error"
    TYPE_MISMATCH = "type_mismatch"
    OTHER = "other"


# PG error code → ErrorType
_PG_CODE_MAP: dict[str, ErrorType] = {
    "42P01": ErrorType.TABLE_NOT_FOUND,   # undefined_table
    "42703": ErrorType.COLUMN_NOT_FOUND,  # undefined_column
    "42601": ErrorType.SQL_SYNTAX_ERROR,  # syntax_error
    "42883": ErrorType.TYPE_MISMATCH,      # undefined_function (often type mismatch)
    "42804": ErrorType.TYPE_MISMATCH,      # datatype_mismatch
}

# MySQL error number → ErrorType
_MYSQL_ERRNO_MAP: dict[int, ErrorType] = {
    1146: ErrorType.TABLE_NOT_FOUND,       # Table doesn't exist
    1054: ErrorType.COLUMN_NOT_FOUND,      # Unknown column
    1064: ErrorType.SQL_SYNTAX_ERROR,      # Syntax error
    1055: ErrorType.TYPE_MISMATCH,         # incompatible types (GROUP BY, etc)
}

# Regex fallbacks for error messages
_REGEX_FALLBACKS: list[tuple[re.Pattern, ErrorType]] = [
    (re.compile(r"(?i)relation\s+[\"'].*?[\"']\s+does\s+not\s+exist"), ErrorType.TABLE_NOT_FOUND),
    (re.compile(r"(?i)column\s+[\"'].*?[\"']\s+does\s+not\s+exist"), ErrorType.COLUMN_NOT_FOUND),
    (re.compile(r"(?i)table\s+['\"].*?['\"]\s+doesn'?t\s+exist"), ErrorType.TABLE_NOT_FOUND),
    (re.compile(r"(?i)unknown\s+column\s+['\"]"), ErrorType.COLUMN_NOT_FOUND),
    (re.compile(r"(?i)syntax\s+error"), ErrorType.SQL_SYNTAX_ERROR),
    (re.compile(r"(?i)cannot\s+cast|type\s+mismatch|incompatible\s+types"), ErrorType.TYPE_MISMATCH),
]


def classify_error(message: str, engine: str = "postgresql", *, pgcode: str | None = None, errno: int | None = None) -> ErrorType:
    """Classify a DB error into a healing-relevant ErrorType."""
    if engine == "postgresql" and pgcode:
        typ = _PG_CODE_MAP.get(pgcode)
        if typ:
            return typ
    if engine == "mysql" and errno is not None:
        typ = _MYSQL_ERRNO_MAP.get(errno)
        if typ:
            return typ
    for pattern, typ in _REGEX_FALLBACKS:
        if pattern.search(message):
            return typ
    return ErrorType.OTHER
