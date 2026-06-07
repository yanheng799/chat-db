"""L1 data pattern detection — aggregate query builder and result parser.

Builds a single aggregate query per table that computes:
- ``total_rows`` — total row count (or estimate from system statistics)
- Per-column: ``distinct_count``, ``null_count``, ``min``, ``max``, ``values``

The query builder produces SQL for both PostgreSQL and MySQL dialects,
with optional ``TABLESAMPLE`` (PG) / ``LIMIT`` (MySQL) for large tables.

Enum detection is a pure function that applies the threshold rules from
the acceptance criteria: ``distinct / total < 0.05`` **and**
``distinct ≤ 20``.
"""

from __future__ import annotations

from typing import Any

# Numeric type patterns — used to decide whether to include MIN/MAX
_NUMERIC_TYPES = frozenset(
    {
        "integer",
        "bigint",
        "smallint",
        "int",
        "tinyint",
        "mediumint",
        "decimal",
        "numeric",
        "real",
        "double",
        "float",
        "double precision",
        "money",
        "serial",
        "bigserial",
        "smallserial",
        "int2",
        "int4",
        "int8",
        "float4",
        "float8",
        "number",
        "dec",
        "fixed",
    }
)

# Maximum distinct values to collect via array_agg for enum candidates
_MAX_ENUM_VALUES = 20

# Row count above which sampling is used
LARGE_TABLE_THRESHOLD = 1_000_000


# ---------------------------------------------------------------------------
# Pure logic helpers
# ---------------------------------------------------------------------------


def is_numeric_type(data_type: str) -> bool:
    """Return True if *data_type* is a numeric SQL type."""
    return data_type.lower().split("(")[0].strip() in _NUMERIC_TYPES


def detect_enum_fields(
    total_rows: int,
    column_stats: dict[str, dict[str, Any]],
) -> dict[str, bool]:
    """Determine which columns are enum candidates.

    A column is considered an enum when:
    - ``distinct_count / total_rows < 0.05``
    - ``distinct_count ≤ 20``

    Returns a ``{column_name: bool}`` mapping.
    """
    result: dict[str, bool] = {}
    for col_name, stats in column_stats.items():
        dc = stats.get("distinct_count", 0)
        if total_rows <= 0 or dc <= 0:
            result[col_name] = False
            continue
        ratio = dc / total_rows
        result[col_name] = ratio < 0.05 and dc <= _MAX_ENUM_VALUES
    return result


def should_use_sampling(estimated_rows: int) -> bool:
    """Return True if aggregate queries should use sampling for this table."""
    return estimated_rows > LARGE_TABLE_THRESHOLD


# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------


def build_aggregate_query(
    table_name: str,
    schema_name: str | None,
    columns: list[Any],
    engine_type: str,
    use_sampling: bool = False,
) -> str:
    """Build a single aggregate query covering all columns of a table.

    *columns* items need ``.column_name`` and ``.data_type`` attributes.

    Raises :class:`ValueError` when *columns* is empty.
    """
    if not columns:
        raise ValueError("Cannot build aggregate query with no columns")

    if engine_type == "postgresql":
        return _build_pg_query(table_name, schema_name, columns, use_sampling)
    else:
        return _build_mysql_query(table_name, columns, use_sampling)


def _build_pg_query(
    table_name: str,
    schema_name: str | None,
    columns: list[Any],
    use_sampling: bool,
) -> str:
    fqn = f'"{schema_name}"."{table_name}"' if schema_name else f'"{table_name}"'

    select_parts: list[str] = ["COUNT(*) AS total_rows"]

    for col in columns:
        cn = col.column_name
        quoted = f'"{cn}"'
        select_parts.append(f"COUNT(DISTINCT {quoted}) AS {cn}__distinct")
        select_parts.append(f"COUNT(*) FILTER (WHERE {quoted} IS NULL) AS {cn}__null_count")
        # Collect distinct values for potential enum detection
        select_parts.append(
            f"(SELECT array_agg(DISTINCT t ORDER BY t) "
            f"FROM unnest(array_agg({quoted})) t "
            f"WHERE t IS NOT NULL LIMIT {_MAX_ENUM_VALUES}) AS {cn}__values"
        )
        if is_numeric_type(col.data_type):
            select_parts.append(f"MIN({quoted}) AS {cn}__min")
            select_parts.append(f"MAX({quoted}) AS {cn}__max")

    sample = " TABLESAMPLE SYSTEM (1)" if use_sampling else ""
    return f"SELECT {', '.join(select_parts)} FROM {fqn}{sample}"


def _build_mysql_query(
    table_name: str,
    columns: list[Any],
    use_sampling: bool,
) -> str:
    fqn = f"`{table_name}`"

    select_parts: list[str] = ["COUNT(*) AS total_rows"]

    for col in columns:
        cn = col.column_name
        bt = f"`{cn}`"
        select_parts.append(f"COUNT(DISTINCT {bt}) AS {cn}__distinct")
        select_parts.append(f"SUM(CASE WHEN {bt} IS NULL THEN 1 ELSE 0 END) AS {cn}__null_count")
        # MySQL: collect distinct values using GROUP_CONCAT (limited)
        select_parts.append(f"NULLIF(GROUP_CONCAT(DISTINCT {bt} ORDER BY {bt} SEPARATOR '||'), '') AS {cn}__values")
        if is_numeric_type(col.data_type):
            select_parts.append(f"MIN({bt}) AS {cn}__min")
            select_parts.append(f"MAX({bt}) AS {cn}__max")

    if use_sampling:
        return f"SELECT {', '.join(select_parts)} FROM {fqn} LIMIT 10000"
    return f"SELECT {', '.join(select_parts)} FROM {fqn}"


# ---------------------------------------------------------------------------
# Result parser
# ---------------------------------------------------------------------------


def parse_aggregate_results(
    row: dict[str, Any],
    columns: list[Any],
) -> dict[str, dict[str, Any]]:
    """Parse a single aggregate result row into per-column stats.

    Returns ``{column_name: {distinct_count, null_count, values, min?, max?}}``.
    """
    total_rows = row.get("total_rows", 0)
    results: dict[str, dict[str, Any]] = {}

    for col in columns:
        cn = col.column_name
        entry: dict[str, Any] = {
            "distinct_count": row.get(f"{cn}__distinct", 0) or 0,
            "null_count": row.get(f"{cn}__null_count", 0) or 0,
        }

        # Parse values
        raw_values = row.get(f"{cn}__values")
        if raw_values is None:
            entry["values"] = None
        elif isinstance(raw_values, str):
            # MySQL returns ||-separated string
            entry["values"] = [v.strip() for v in raw_values.split("||") if v.strip()] if raw_values else []
        elif isinstance(raw_values, (list, tuple)):
            entry["values"] = list(raw_values)
        else:
            entry["values"] = None

        # Numeric range (only for numeric columns)
        if is_numeric_type(col.data_type):
            entry["min"] = row.get(f"{cn}__min")
            entry["max"] = row.get(f"{cn}__max")

        results[cn] = entry

    results["__total_rows__"] = total_rows
    return results


# ---------------------------------------------------------------------------
# Estimated row count queries
# ---------------------------------------------------------------------------


def compute_table_estimated_rows(
    table_name: str,
    schema_name: str | None,
    engine_type: str,
) -> str:
    """Return a SQL query that estimates the row count of *table_name*.

    For PG: uses ``pg_class.reltuples``.
    For MySQL: uses ``EXPLAIN``.
    """
    if engine_type == "postgresql":
        schema = schema_name or "public"
        return (
            "SELECT c.reltuples::bigint AS estimate "
            f"FROM pg_class c "
            f"JOIN pg_namespace n ON n.oid = c.relnamespace "
            f"WHERE c.relname = '{table_name}' AND n.nspname = '{schema}'"
        )
    else:
        return f"EXPLAIN SELECT 1 FROM `{table_name}`"
