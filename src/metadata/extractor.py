from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

PG_SYSTEM_SCHEMAS = frozenset({"pg_catalog", "information_schema", "pg_toast"})
PG_TEMP_PATTERN = "pg_temp_"

MYSQL_SYSTEM_DATABASES = frozenset({"mysql", "information_schema", "performance_schema", "sys"})


@runtime_checkable
class MetadataExtractor(Protocol):
    """Protocol for metadata extraction from target data sources."""

    async def extract(self, schema_whitelist: list[dict] | None = None) -> dict[str, list[dict]]:
        """Extract all metadata. Returns dict with keys: tables, columns, indexes, foreign_keys."""


class PgMetadataExtractor:
    """Extracts PostgreSQL metadata from information_schema and pg_catalog."""

    def __init__(self, connection) -> None:
        self._connection = connection

    async def extract(self, schema_whitelist: list[dict] | None = None) -> dict[str, list[dict]]:
        allowed_schemas = None
        if schema_whitelist:
            allowed_schemas = {s["schema"] for s in schema_whitelist}

        raw_tables = await self._fetch_tables(self._connection, allowed_schemas)
        tables = [
            t
            for t in raw_tables
            if t["table_schema"] not in PG_SYSTEM_SCHEMAS
            and not t["table_schema"].startswith(PG_TEMP_PATTERN)
            and (allowed_schemas is None or t["table_schema"] in allowed_schemas)
        ]

        raw_columns = await self._fetch_columns(self._connection, allowed_schemas)
        columns = [
            c
            for c in raw_columns
            if c["table_schema"] not in PG_SYSTEM_SCHEMAS
            and not c["table_schema"].startswith(PG_TEMP_PATTERN)
            and (allowed_schemas is None or c["table_schema"] in allowed_schemas)
        ]

        raw_indexes = await self._fetch_indexes(self._connection, allowed_schemas)
        indexes = [
            i
            for i in raw_indexes
            if i["table_schema"] not in PG_SYSTEM_SCHEMAS
            and not i["table_schema"].startswith(PG_TEMP_PATTERN)
            and (allowed_schemas is None or i["table_schema"] in allowed_schemas)
        ]

        raw_fks = await self._fetch_foreign_keys(self._connection, allowed_schemas)
        foreign_keys = [
            f
            for f in raw_fks
            if f["table_schema"] not in PG_SYSTEM_SCHEMAS
            and not f["table_schema"].startswith(PG_TEMP_PATTERN)
            and (allowed_schemas is None or f["table_schema"] in allowed_schemas)
        ]

        return {
            "tables": tables,
            "columns": columns,
            "indexes": indexes,
            "foreign_keys": foreign_keys,
        }

    async def _fetch_tables(self, conn, schemas) -> list[dict[str, Any]]:
        return []

    async def _fetch_columns(self, conn, schemas) -> list[dict[str, Any]]:
        return []

    async def _fetch_indexes(self, conn, schemas) -> list[dict[str, Any]]:
        return []

    async def _fetch_foreign_keys(self, conn, schemas) -> list[dict[str, Any]]:
        return []


class MySqlMetadataExtractor:
    """Extracts MySQL metadata from information_schema."""

    def __init__(self, connection) -> None:
        self._connection = connection

    async def extract(self, schema_whitelist: list[dict] | None = None) -> dict[str, list[dict]]:
        allowed_databases = None
        if schema_whitelist:
            allowed_databases = {s["schema"] for s in schema_whitelist}

        raw_tables = await self._fetch_tables(self._connection, allowed_databases)
        tables = [
            t
            for t in raw_tables
            if t["table_schema"] not in MYSQL_SYSTEM_DATABASES
            and (allowed_databases is None or t["table_schema"] in allowed_databases)
        ]

        raw_columns = await self._fetch_columns(self._connection, allowed_databases)
        columns = [
            c
            for c in raw_columns
            if c["table_schema"] not in MYSQL_SYSTEM_DATABASES
            and (allowed_databases is None or c["table_schema"] in allowed_databases)
        ]

        raw_indexes = await self._fetch_indexes(self._connection, allowed_databases)
        indexes = [
            i
            for i in raw_indexes
            if i["table_schema"] not in MYSQL_SYSTEM_DATABASES
            and (allowed_databases is None or i["table_schema"] in allowed_databases)
        ]

        raw_fks = await self._fetch_foreign_keys(self._connection, allowed_databases)
        foreign_keys = [
            f
            for f in raw_fks
            if f["table_schema"] not in MYSQL_SYSTEM_DATABASES
            and (allowed_databases is None or f["table_schema"] in allowed_databases)
        ]

        return {
            "tables": tables,
            "columns": columns,
            "indexes": indexes,
            "foreign_keys": foreign_keys,
        }

    async def _fetch_tables(self, conn, schemas) -> list[dict[str, Any]]:
        return []

    async def _fetch_columns(self, conn, schemas) -> list[dict[str, Any]]:
        return []

    async def _fetch_indexes(self, conn, schemas) -> list[dict[str, Any]]:
        return []

    async def _fetch_foreign_keys(self, conn, schemas) -> list[dict[str, Any]]:
        return []
