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
        query = """
            SELECT table_schema, table_name, table_type,
                   obj_description(
                       (quote_ident(table_schema) || '.' || quote_ident(table_name))::regclass,
                       'pg_class'
                   ) AS table_comment
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
              AND table_schema NOT IN ('pg_catalog', 'information_schema')
        """
        result = await conn.exec_driver_sql(query)
        return [dict(zip(result.keys(), row)) for row in result.fetchall()]

    async def _fetch_columns(self, conn, schemas) -> list[dict[str, Any]]:
        query = """
            SELECT c.table_schema, c.table_name, c.column_name,
                   c.data_type, c.is_nullable, c.column_default,
                   c.ordinal_position::int AS ordinal_position,
                   pgd.description AS column_comment,
                   CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END AS is_primary_key
            FROM information_schema.columns c
            JOIN pg_catalog.pg_class pct ON pct.relname = c.table_name
            JOIN pg_catalog.pg_namespace pns ON pns.oid = pct.relnamespace
                AND pns.nspname = c.table_schema
            LEFT JOIN pg_catalog.pg_description pgd
                ON pgd.objoid = pct.oid
                AND pgd.objsubid = c.ordinal_position::int
            LEFT JOIN (
                SELECT ku.table_schema, ku.table_name, ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                    ON tc.constraint_name = ku.constraint_name
                    AND tc.table_schema = ku.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
            ) pk ON pk.table_schema = c.table_schema
                AND pk.table_name = c.table_name
                AND pk.column_name = c.column_name
            WHERE c.table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY c.table_schema, c.table_name, c.ordinal_position
        """
        result = await conn.exec_driver_sql(query)
        return [dict(zip(result.keys(), row)) for row in result.fetchall()]

    async def _fetch_indexes(self, conn, schemas) -> list[dict[str, Any]]:
        query = """
            SELECT n.nspname AS table_schema, t.relname AS table_name,
                   i.relname AS index_name,
                   pg_get_indexdef(i.oid) AS index_def,
                   am.amname AS index_type,
                   indisunique AS is_unique,
                   indisprimary AS is_primary
            FROM pg_index x
            JOIN pg_class t ON t.oid = x.indrelid
            JOIN pg_class i ON i.oid = x.indexrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            JOIN pg_am am ON am.oid = i.relam
            WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
        """
        result = await conn.exec_driver_sql(query)
        return [dict(zip(result.keys(), row)) for row in result.fetchall()]

    async def _fetch_foreign_keys(self, conn, schemas) -> list[dict[str, Any]]:
        query = """
            SELECT tc.table_schema, tc.table_name, kcu.column_name,
                   ccu.table_schema AS foreign_table_schema,
                   ccu.table_name AS foreign_table_name,
                   ccu.column_name AS foreign_column_name,
                   tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.referential_constraints rc
                ON tc.constraint_name = rc.constraint_name
                AND tc.table_schema = rc.constraint_schema
            JOIN information_schema.key_column_usage ccu
                ON rc.unique_constraint_name = ccu.constraint_name
                AND rc.unique_constraint_schema = ccu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            ORDER BY tc.table_schema, tc.table_name, kcu.column_name
        """
        result = await conn.exec_driver_sql(query)
        return [dict(zip(result.keys(), row)) for row in result.fetchall()]


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
        query = """
            SELECT table_schema, table_name, table_type, table_comment
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
        """
        result = await conn.exec_driver_sql(query)
        return [dict(zip(result.keys(), row)) for row in result.fetchall()]

    async def _fetch_columns(self, conn, schemas) -> list[dict[str, Any]]:
        query = """
            SELECT c.table_schema, c.table_name, c.column_name,
                   c.data_type, c.is_nullable, c.column_default,
                   c.ordinal_position, c.column_comment,
                   CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END AS is_primary_key
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT ku.table_schema, ku.table_name, ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                    ON tc.constraint_name = ku.constraint_name
                    AND tc.table_schema = ku.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
            ) pk ON pk.table_schema = c.table_schema
                AND pk.table_name = c.table_name
                AND pk.column_name = c.column_name
            ORDER BY c.table_schema, c.table_name, c.ordinal_position
        """
        result = await conn.exec_driver_sql(query)
        return [dict(zip(result.keys(), row)) for row in result.fetchall()]

    async def _fetch_indexes(self, conn, schemas) -> list[dict[str, Any]]:
        query = """
            SELECT table_schema, table_name, index_name,
                   GROUP_CONCAT(column_name ORDER BY seq_in_index) AS columns,
                   non_unique, index_type
            FROM information_schema.statistics
            WHERE table_schema NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
            GROUP BY table_schema, table_name, index_name, non_unique, index_type
        """
        result = await conn.exec_driver_sql(query)
        return [dict(zip(result.keys(), row)) for row in result.fetchall()]

    async def _fetch_foreign_keys(self, conn, schemas) -> list[dict[str, Any]]:
        query = """
            SELECT tc.table_schema, tc.table_name, kcu.column_name,
                   kcu.referenced_table_schema AS foreign_table_schema,
                   kcu.referenced_table_name AS foreign_table_name,
                   kcu.referenced_column_name AS foreign_column_name,
                   tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            ORDER BY tc.table_schema, tc.table_name, kcu.column_name
        """
        result = await conn.exec_driver_sql(query)
        return [dict(zip(result.keys(), row)) for row in result.fetchall()]
