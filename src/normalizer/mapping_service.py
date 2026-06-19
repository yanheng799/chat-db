"""Value mapping center CRUD + seed + cleanup (issue #24)."""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from metadata.models import MetadataColumn, MetadataTable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enum alias CRUD
# ---------------------------------------------------------------------------


async def upsert_enum_alias(
    session: AsyncSession,
    data_source_id: uuid.UUID,
    table_name: str,
    column_name: str,
    value: str,
    *,
    display: str | None = None,
    aliases: list[str] | None = None,
) -> None:
    display = display or value
    aliases = aliases or []
    await session.execute(
        text(
            "INSERT INTO value_enum_mappings (id, data_source_id, table_name, column_name, value, display, aliases) "
            "VALUES (:id, :ds, :tbl, :col, :val, :disp, (:als)::jsonb) "
            "ON CONFLICT (data_source_id, table_name, column_name, value) "
            "DO UPDATE SET display=EXCLUDED.display, aliases=EXCLUDED.aliases, updated_at=now()"
        ),
        {"id": uuid.uuid4(), "ds": data_source_id, "tbl": table_name, "col": column_name, "val": value, "disp": display, "als": json.dumps(aliases, ensure_ascii=False)},
    )
    await session.commit()


async def list_enum_aliases(
    session: AsyncSession, data_source_id: uuid.UUID
) -> list[dict]:
    rows = await session.execute(
        text("SELECT * FROM value_enum_mappings WHERE data_source_id=:ds ORDER BY table_name, column_name, value"),
        {"ds": data_source_id},
    )
    return [dict(r._mapping) for r in rows]


async def delete_enum_alias(session: AsyncSession, mapping_id: uuid.UUID) -> bool:
    result = await session.execute(
        text("DELETE FROM value_enum_mappings WHERE id=:id"), {"id": mapping_id}
    )
    await session.commit()
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# Region dict CRUD
# ---------------------------------------------------------------------------


async def upsert_region(
    session: AsyncSession,
    data_source_id: uuid.UUID,
    *,
    code: str,
    parent_code: str | None,
    level: str,
    name: str,
    aliases: list[str] | None = None,
) -> None:
    aliases = aliases or []
    await session.execute(
        text(
            "INSERT INTO value_region_dict (id, data_source_id, code, parent_code, level, name, aliases) "
            "VALUES (:id, :ds, :code, :pc, :lv, :nm, (:als)::jsonb) "
            "ON CONFLICT DO NOTHING"
        ),
        {"id": uuid.uuid4(), "ds": data_source_id, "code": code, "pc": parent_code, "lv": level, "nm": name, "als": json.dumps(aliases, ensure_ascii=False)},
    )
    await session.commit()


async def list_regions(
    session: AsyncSession, data_source_id: uuid.UUID
) -> list[dict]:
    rows = await session.execute(
        text("SELECT * FROM value_region_dict WHERE data_source_id=:ds ORDER BY level, code"),
        {"ds": data_source_id},
    )
    return [dict(r._mapping) for r in rows]


# ---------------------------------------------------------------------------
# Name abbreviation CRUD
# ---------------------------------------------------------------------------


async def upsert_name_mapping(
    session: AsyncSession,
    data_source_id: uuid.UUID,
    *,
    short_name: str,
    full_name: str,
    target_table: str | None = None,
    aliases: list[str] | None = None,
) -> None:
    aliases = aliases or []
    await session.execute(
        text(
            "INSERT INTO value_name_mappings (id, data_source_id, short_name, full_name, target_table, aliases) "
            "VALUES (:id, :ds, :sn, :fn, :tt, (:als)::jsonb) "
            "ON CONFLICT (data_source_id, short_name) "
            "DO UPDATE SET full_name=EXCLUDED.full_name, aliases=EXCLUDED.aliases"
        ),
        {"id": uuid.uuid4(), "ds": data_source_id, "sn": short_name, "fn": full_name, "tt": target_table, "als": json.dumps(aliases, ensure_ascii=False)},
    )
    await session.commit()


async def list_name_mappings(
    session: AsyncSession, data_source_id: uuid.UUID
) -> list[dict]:
    rows = await session.execute(
        text("SELECT * FROM value_name_mappings WHERE data_source_id=:ds ORDER BY short_name"),
        {"ds": data_source_id},
    )
    return [dict(r._mapping) for r in rows]


# ---------------------------------------------------------------------------
# Seed & cleanup
# ---------------------------------------------------------------------------


async def auto_collect_enum_seeds(
    session: AsyncSession, data_source_id: uuid.UUID
) -> int:
    """Collect enum seeds from L1 detected_enum_values, returns count inserted."""
    tables_result = await session.execute(
        select(MetadataTable).where(MetadataTable.data_source_id == data_source_id)
    )
    table_by_id = {t.id: t for t in tables_result.scalars().all()}
    cols_result = await session.execute(
        select(MetadataColumn).where(
            MetadataColumn.table_id.in_([t.id for t in table_by_id.values()]),
            MetadataColumn.detected_enum_values.is_not(None),
        )
    )
    count = 0
    for col in cols_result.scalars().all():
        tbl = table_by_id.get(col.table_id)
        if tbl is None:
            continue
        for val in (col.detected_enum_values or []):
            await upsert_enum_alias(
                session, data_source_id,
                table_name=tbl.table_name, column_name=col.column_name,
                value=str(val), display=str(val), aliases=[],
            )
            count += 1
    return count


async def cleanup_mappings(
    session: AsyncSession, data_source_id: uuid.UUID
) -> None:
    """Delete all mapping records for a data source (on DS deletion)."""
    for tbl in ("value_enum_mappings", "value_region_dict", "value_name_mappings"):
        await session.execute(
            text(f"DELETE FROM {tbl} WHERE data_source_id=:ds"), {"ds": data_source_id}
        )
    await session.commit()
