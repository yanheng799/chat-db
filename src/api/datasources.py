from __future__ import annotations

import asyncio
import contextlib
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import (
    ConnectionTestResponse,
    DataSourceCreate,
    DataSourceResponse,
    DataSourceUpdate,
    MetadataOverview,
    SyncLogResponse,
    SyncRequest,
    SyncResponse,
)
from config.data_source_model import DataSource
from config.database import get_session
from config.encryption import decrypt_value, encrypt_value
from config.settings import Settings
from db.connection import ConnectionManager
from metadata.extractor import MySqlMetadataExtractor, PgMetadataExtractor
from metadata.models import (
    MetadataChangeLog,
    MetadataColumn,
    MetadataSyncLog,
    MetadataTable,
)
from metadata.sync import compute_diff

router = APIRouter(prefix="/api/datasources", tags=["datasources"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_connection_manager = ConnectionManager()


def _model_to_response(ds: DataSource) -> DataSourceResponse:
    return DataSourceResponse(
        id=ds.id,
        name=ds.name,
        engine=ds.engine,
        host=ds.host,
        port=ds.port,
        username=ds.username,
        database=ds.database,
        schema_whitelist=ds.schema_whitelist,
        is_active=ds.is_active,
        created_at=ds.created_at,
        updated_at=ds.updated_at,
    )


def _get_encryption_key() -> str:
    settings = Settings()
    if not settings.encryption_key:
        raise HTTPException(status_code=500, detail="ENCRYPTION_KEY is not configured")
    return settings.encryption_key


async def _get_ds_or_404(ds_id: uuid.UUID, session: AsyncSession) -> DataSource:
    ds = await session.get(DataSource, ds_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="Data source not found")
    return ds


# ── CRUD endpoints (from Issue #1) ──────────────────────────────


@router.post("", status_code=201)
async def create_data_source(
    payload: DataSourceCreate,
    session: SessionDep,
) -> DataSourceResponse:
    key = _get_encryption_key()
    existing = await session.execute(select(DataSource).where(DataSource.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Data source name already exists")

    ds = DataSource(
        name=payload.name,
        engine=payload.engine,
        host=payload.host,
        port=payload.port,
        username=payload.username,
        password_encrypted=encrypt_value(payload.password, key),
        database=payload.database,
        schema_whitelist=payload.schema_whitelist,
    )
    session.add(ds)
    await session.commit()
    await session.refresh(ds)
    return _model_to_response(ds)


@router.get("")
async def list_data_sources(session: SessionDep) -> list[DataSourceResponse]:
    result = await session.execute(select(DataSource).order_by(DataSource.created_at))
    return [_model_to_response(ds) for ds in result.scalars().all()]


@router.get("/{ds_id}")
async def get_data_source(ds_id: uuid.UUID, session: SessionDep) -> DataSourceResponse:
    return _model_to_response(await _get_ds_or_404(ds_id, session))


@router.put("/{ds_id}")
async def update_data_source(ds_id: uuid.UUID, payload: DataSourceUpdate, session: SessionDep) -> DataSourceResponse:
    ds = await _get_ds_or_404(ds_id, session)
    update_data = payload.model_dump(exclude_unset=True)
    if "password" in update_data:
        key = _get_encryption_key()
        ds.password_encrypted = encrypt_value(update_data.pop("password"), key)
    if "name" in update_data:
        existing = await session.execute(
            select(DataSource).where(DataSource.name == update_data["name"], DataSource.id != ds_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="Data source name already exists")
    for field, value in update_data.items():
        setattr(ds, field, value)
    await session.commit()
    await session.refresh(ds)
    return _model_to_response(ds)


@router.delete("/{ds_id}", status_code=204)
async def delete_data_source(ds_id: uuid.UUID, session: SessionDep) -> None:
    ds = await _get_ds_or_404(ds_id, session)
    await session.delete(ds)
    await session.commit()


@router.post("/{ds_id}/test")
async def test_connection(ds_id: uuid.UUID, session: SessionDep) -> ConnectionTestResponse:
    ds = await _get_ds_or_404(ds_id, session)
    key = _get_encryption_key()
    password = decrypt_value(ds.password_encrypted, key)
    try:
        from sqlalchemy import create_engine, text

        if ds.engine == "postgresql":
            sync_url = f"postgresql+psycopg2://{ds.username}:{password}@{ds.host}:{ds.port}/{ds.database}"
        else:
            sync_url = f"mysql+pymysql://{ds.username}:{password}@{ds.host}:{ds.port}/{ds.database}"
        test_engine = create_engine(sync_url, pool_pre_ping=True)
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        test_engine.dispose()
        return ConnectionTestResponse(success=True, message="Connection successful")
    except Exception as e:
        return ConnectionTestResponse(success=False, message=str(e))


# ── Activate / Deactivate ───────────────────────────────────────


@router.post("/{ds_id}/activate")
async def activate_data_source(ds_id: uuid.UUID, session: SessionDep) -> DataSourceResponse:
    ds = await _get_ds_or_404(ds_id, session)

    # Deactivate currently active source
    active_result = await session.execute(select(DataSource).where(DataSource.is_active.is_(True)))
    currently_active = active_result.scalars().all()
    for other in currently_active:
        if other.id != ds.id:
            other.is_active = False
            _connection_manager.dispose_sync(other.id)

    ds.is_active = True
    await session.commit()
    await session.refresh(ds)

    # Check if metadata exists for this data source
    meta_result = await session.execute(select(MetadataTable).where(MetadataTable.data_source_id == ds_id).limit(1))
    has_metadata = meta_result.scalar_one_or_none() is not None

    if not has_metadata:
        key = _get_encryption_key()
        ds_config = {
            "id": str(ds.id),
            "engine": ds.engine,
            "host": ds.host,
            "port": ds.port,
            "username": ds.username,
            "password": decrypt_value(ds.password_encrypted, key),
            "database": ds.database,
            "schema_whitelist": ds.schema_whitelist,
        }
        asyncio.create_task(_run_metadata_extraction(ds.id, ds_config))

    return _model_to_response(ds)


@router.post("/{ds_id}/deactivate")
async def deactivate_data_source(ds_id: uuid.UUID, session: SessionDep) -> DataSourceResponse:
    ds = await _get_ds_or_404(ds_id, session)
    ds.is_active = False
    _connection_manager.dispose_sync(ds.id)
    await session.commit()
    await session.refresh(ds)
    return _model_to_response(ds)


# ── Metadata extraction (background task) ───────────────────────


async def _run_metadata_extraction(datasource_id: uuid.UUID, ds_config: dict) -> None:
    """Run full metadata extraction as a background task."""
    # Create independent session for background task
    from config.database import get_session as _get_session

    async for session in _get_session():
        sync_log_id = uuid.uuid4()
        sync_log = MetadataSyncLog(
            id=sync_log_id,
            data_source_id=datasource_id,
            sync_type="full",
            status="running",
            started_at=datetime.now(),
        )
        session.add(sync_log)
        try:
            await session.commit()
        except Exception:
            return

        engine_config = {
            "id": ds_config["id"],
            "engine": ds_config["engine"],
            "host": ds_config["host"],
            "port": ds_config["port"],
            "username": ds_config["username"],
            "password": ds_config["password"],
            "database": ds_config["database"],
        }
        engine = _connection_manager.create_engine(engine_config)

        try:
            async with engine.connect() as conn:
                if ds_config["engine"] == "mysql":
                    extractor = MySqlMetadataExtractor(conn)
                else:
                    extractor = PgMetadataExtractor(conn)
                data = await extractor.extract(ds_config.get("schema_whitelist"))

            tables_count = 0
            columns_count = 0
            for t_data in data["tables"]:
                table_id = uuid.uuid4()
                session.add(
                    MetadataTable(
                        id=table_id,
                        data_source_id=datasource_id,
                        schema_name=t_data["table_schema"],
                        table_name=t_data["table_name"],
                        table_type=t_data.get("table_type", "BASE TABLE"),
                        table_comment=t_data.get("table_comment"),
                    )
                )
                tables_count += 1

                table_cols = [
                    c
                    for c in data["columns"]
                    if c["table_schema"] == t_data["table_schema"] and c["table_name"] == t_data["table_name"]
                ]
                for c_data in table_cols:
                    session.add(
                        MetadataColumn(
                            id=uuid.uuid4(),
                            table_id=table_id,
                            column_name=c_data["column_name"],
                            data_type=c_data.get("data_type", ""),
                            is_nullable=c_data.get("is_nullable", "YES") == "YES",
                            default_value=c_data.get("column_default"),
                            column_comment=c_data.get("column_comment"),
                            is_primary_key=c_data.get("is_primary_key", False),
                            ordinal_position=c_data.get("ordinal_position", 0),
                        )
                    )
                    columns_count += 1

            sync_log.status = "success"
            sync_log.finished_at = datetime.now()
            sync_log.tables_added = tables_count
            sync_log.columns_changed = columns_count
            await session.commit()
        except Exception as e:
            result = await session.execute(select(MetadataSyncLog).where(MetadataSyncLog.id == sync_log_id))
            log = result.scalar_one_or_none()
            if log is not None:
                log.status = "failed"
                log.finished_at = datetime.now()
                log.error_message = str(e)
            with contextlib.suppress(Exception):
                await session.commit()
        finally:
            _connection_manager.dispose_sync(ds_config["id"])


# ── Metadata & Sync-Logs queries ────────────────────────────────


@router.get("/{ds_id}/metadata")
async def get_metadata_overview(ds_id: uuid.UUID, session: SessionDep) -> MetadataOverview:
    await _get_ds_or_404(ds_id, session)

    table_count_result = await session.execute(select(MetadataTable).where(MetadataTable.data_source_id == ds_id))
    tables = table_count_result.scalars().all()
    table_count = len(tables)

    table_ids = [t.id for t in tables]
    column_count = 0
    if table_ids:
        col_result = await session.execute(select(MetadataColumn).where(MetadataColumn.table_id.in_(table_ids)))
        column_count = len(col_result.scalars().all())

    return MetadataOverview(table_count=table_count, column_count=column_count)


@router.get("/{ds_id}/sync-logs")
async def get_sync_logs(ds_id: uuid.UUID, session: SessionDep) -> list[SyncLogResponse]:
    await _get_ds_or_404(ds_id, session)
    result = await session.execute(
        select(MetadataSyncLog)
        .where(MetadataSyncLog.data_source_id == ds_id)
        .order_by(MetadataSyncLog.started_at.desc())
    )
    logs = result.scalars().all()
    return [SyncLogResponse.model_validate(log) for log in logs]


# ── Manual Sync ──────────────────────────────────────────────────


@router.post("/{ds_id}/sync", status_code=202)
async def trigger_sync(
    ds_id: uuid.UUID,
    session: SessionDep,
    payload: SyncRequest | None = None,
) -> SyncResponse:
    ds = await _get_ds_or_404(ds_id, session)
    # Concurrent sync prevention
    running_result = await session.execute(
        select(MetadataSyncLog).where(
            MetadataSyncLog.data_source_id == ds_id,
            MetadataSyncLog.status == "running",
        )
    )
    if running_result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="A sync is already in progress for this data source")

    scope_items = payload.table_scope if payload and payload.table_scope else None
    scope_list = [{"schema": s.schema_name, "table": s.table} for s in scope_items] if scope_items else None

    sync_log_id = uuid.uuid4()
    sync_log = MetadataSyncLog(
        id=sync_log_id,
        data_source_id=ds_id,
        sync_type="manual",
        scope=scope_list,
        status="running",
        started_at=datetime.now(),
    )
    session.add(sync_log)
    await session.commit()

    key = _get_encryption_key()
    ds_config = {
        "id": str(ds.id),
        "engine": ds.engine,
        "host": ds.host,
        "port": ds.port,
        "username": ds.username,
        "password": decrypt_value(ds.password_encrypted, key),
        "database": ds.database,
        "schema_whitelist": ds.schema_whitelist,
    }
    asyncio.create_task(_run_sync(ds.id, sync_log_id, ds_config, scope_items))

    return SyncResponse(
        sync_log_id=sync_log_id,
        message="Sync started in background",
    )


async def _run_sync(
    datasource_id: uuid.UUID,
    sync_log_id: uuid.UUID,
    ds_config: dict,
    table_scope: list | None = None,
) -> None:
    from config.database import get_session as _get_session

    async for session in _get_session():
        engine_config = {
            "id": ds_config["id"],
            "engine": ds_config["engine"],
            "host": ds_config["host"],
            "port": ds_config["port"],
            "username": ds_config["username"],
            "password": ds_config["password"],
            "database": ds_config["database"],
        }
        engine = _connection_manager.create_engine(engine_config)

        try:
            async with engine.connect() as conn:
                if ds_config["engine"] == "mysql":
                    from metadata.extractor import MySqlMetadataExtractor as Ex
                else:
                    from metadata.extractor import PgMetadataExtractor as Ex
                extractor = Ex(conn)
                current = await extractor.extract(ds_config.get("schema_whitelist"))

            # Build stored metadata from DB
            stored_tables = await _build_stored_metadata(datasource_id, session)

            # Filter current data if table_scope specified
            if table_scope:
                scope_keys = {(s.schema_name, s.table) for s in table_scope}
                current = {
                    "tables": [t for t in current["tables"] if (t["table_schema"], t["table_name"]) in scope_keys],
                    "columns": [c for c in current["columns"] if (c["table_schema"], c["table_name"]) in scope_keys],
                    "indexes": [i for i in current["indexes"] if (i["table_schema"], i["table_name"]) in scope_keys],
                    "foreign_keys": [
                        f for f in current["foreign_keys"] if (f["table_schema"], f["table_name"]) in scope_keys
                    ],
                }

            changes = compute_diff(current, stored_tables)

            # Record change logs and apply changes
            for ch in changes:
                session.add(
                    MetadataChangeLog(
                        id=uuid.uuid4(),
                        sync_log_id=sync_log_id,
                        data_source_id=datasource_id,
                        change_type=ch["change_type"],
                        schema_name=ch["schema_name"],
                        table_name=ch["table_name"],
                        object_name=ch["object_name"],
                        before_value=ch["before_value"],
                        after_value=ch["after_value"],
                    )
                )

            # Apply changes to metadata tables
            tables_added = sum(1 for c in changes if c["change_type"] == "table_added")
            tables_removed = sum(1 for c in changes if c["change_type"] == "table_removed")
            cols_changed = sum(1 for c in changes if c["change_type"].startswith(("column_", "index_", "fk_")))

            await _apply_changes(session, changes, datasource_id)

            # Update sync_log
            result = await session.execute(select(MetadataSyncLog).where(MetadataSyncLog.id == sync_log_id))
            log = result.scalar_one_or_none()
            if log is not None:
                log.status = "success"
                log.finished_at = datetime.now()
                log.tables_added = tables_added
                log.tables_removed = tables_removed
                log.columns_changed = cols_changed
            await session.commit()
        except Exception as e:
            result = await session.execute(select(MetadataSyncLog).where(MetadataSyncLog.id == sync_log_id))
            log = result.scalar_one_or_none()
            if log is not None:
                log.status = "failed"
                log.finished_at = datetime.now()
                log.error_message = str(e)
            with contextlib.suppress(Exception):
                await session.commit()
        finally:
            _connection_manager.dispose_sync(ds_config["id"])


async def _build_stored_metadata(datasource_id: uuid.UUID, session) -> dict:
    """Build stored metadata dict from DB for diff comparison."""
    tables_result = await session.execute(select(MetadataTable).where(MetadataTable.data_source_id == datasource_id))
    tables = tables_result.scalars().all()

    stored_tables = []
    stored_columns = []
    stored_indexes = []
    stored_fks = []

    for t in tables:
        stored_tables.append({"table_schema": t.schema_name, "table_name": t.table_name})
        # Columns
        cols = await session.execute(select(MetadataColumn).where(MetadataColumn.table_id == t.id))
        for c in cols.scalars().all():
            stored_columns.append(
                {
                    "table_schema": t.schema_name,
                    "table_name": t.table_name,
                    "column_name": c.column_name,
                    "data_type": c.data_type,
                    "is_nullable": "YES" if c.is_nullable else "NO",
                }
            )
        # Indexes
        from metadata.models import MetadataForeignKey, MetadataIndex

        idxs = await session.execute(select(MetadataIndex).where(MetadataIndex.table_id == t.id))
        for i in idxs.scalars().all():
            stored_indexes.append(
                {
                    "table_schema": t.schema_name,
                    "table_name": t.table_name,
                    "index_name": i.index_name,
                }
            )
        # FKs
        fks = await session.execute(select(MetadataForeignKey).where(MetadataForeignKey.table_id == t.id))
        for f in fks.scalars().all():
            stored_fks.append(
                {
                    "table_schema": t.schema_name,
                    "table_name": t.table_name,
                    "constraint_name": f.constraint_name,
                }
            )

    return {"tables": stored_tables, "columns": stored_columns, "indexes": stored_indexes, "foreign_keys": stored_fks}


async def _apply_changes(session, changes: list[dict], datasource_id: uuid.UUID) -> None:
    """Apply diff changes to metadata tables."""
    for ch in changes:
        if ch["change_type"] == "table_added":
            session.add(
                MetadataTable(
                    id=uuid.uuid4(),
                    data_source_id=datasource_id,
                    schema_name=ch["schema_name"],
                    table_name=ch["table_name"],
                )
            )
        elif ch["change_type"] == "table_removed":
            result = await session.execute(
                select(MetadataTable).where(
                    MetadataTable.data_source_id == datasource_id,
                    MetadataTable.schema_name == ch["schema_name"],
                    MetadataTable.table_name == ch["table_name"],
                )
            )
            table = result.scalar_one_or_none()
            if table is not None:
                await session.delete(table)
    await session.commit()
