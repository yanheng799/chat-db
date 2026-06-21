from __future__ import annotations

import asyncio
import contextlib
import logging
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
    LearningLogResponse,
    LearnResponse,
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
    MetadataLearningLog,
    MetadataSyncLog,
    MetadataTable,
)
from metadata.sync import compute_diff

router = APIRouter(prefix="/api/datasources", tags=["datasources"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]

logger = logging.getLogger(__name__)
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


def _humanize_error(e: Exception) -> str:
    """Translate technical errors into user-readable messages."""
    msg = str(e)
    # Connection / config errors
    if "unexpected keyword argument" in msg:
        return f"数据库驱动配置错误: {msg}"
    if "could not translate host name" in msg.lower() or "nodename nor servname" in msg.lower():
        return "无法解析数据库主机名，请检查主机地址"
    if "Connection refused" in msg or "connection refused" in msg.lower():
        return "数据库拒绝连接，请检查主机和端口是否正确"
    if "password authentication failed" in msg.lower():
        return "数据库密码错误"
    if "timeout" in msg.lower():
        return "数据库连接超时，请检查网络或防火墙"
    if "does not exist" in msg.lower() and "database" in msg.lower():
        return "数据库不存在，请检查数据库名"
    if "Incorrect padding" in msg or "not valid base64" in msg:
        return "加密密钥配置无效，请运行 python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\" 生成新密钥"
    return msg


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

    # Knowledge-base cleanup (Phase 3): app-DB CASCADE does not reach Milvus/Neo4j.
    with contextlib.suppress(Exception):
        from knowledge.graph_store import GraphStore
        from knowledge.lifecycle import cleanup_knowledge_base
        from knowledge.vector_store import VectorStore

        await cleanup_knowledge_base(ds_id, vector_store=VectorStore(), graph_store=GraphStore())


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

            logger.info(
                "Extraction result: %d tables, %d columns, %d indexes, %d fks",
                len(data.get("tables", [])),
                len(data.get("columns", [])),
                len(data.get("indexes", [])),
                len(data.get("foreign_keys", [])),
            )
            if data.get("tables"):
                sample = data["tables"][0]
                logger.info("Sample table: schema=%s name=%s", sample.get("table_schema"), sample.get("table_name"))
            if data.get("columns"):
                sample = data["columns"][0]
                logger.info("Sample column: schema=%s table=%s name=%s",
                            sample.get("table_schema"), sample.get("table_name"), sample.get("column_name"))
            elif data.get("tables"):
                logger.warning(
                    "Tables found but ZERO columns! First table: schema=%s name=%s",
                    data["tables"][0].get("table_schema"),
                    data["tables"][0].get("table_name"),
                )

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

            # Auto-trigger learning after successful extraction
            asyncio.create_task(_run_learning_auto(datasource_id))
        except Exception as e:
            error_msg = f"[后端] {_humanize_error(e)}"
            try:
                result = await session.execute(
                    select(MetadataSyncLog).where(MetadataSyncLog.id == sync_log_id)
                )
                log = result.scalar_one_or_none()
                if log is not None:
                    log.status = "failed"
                    log.finished_at = datetime.now()
                    log.error_message = error_msg
                    await session.commit()
            except Exception:
                pass  # best-effort: at minimum the error is logged to stderr
            logger.exception("Metadata extraction failed for datasource %s", datasource_id)
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
    # Mutex: reject if a learning task is running
    from fastapi import HTTPException

    running_learn = await session.execute(
        select(MetadataLearningLog).where(
            MetadataLearningLog.data_source_id == ds_id,
            MetadataLearningLog.status == "running",
        )
    )
    if running_learn.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="A learning task is already running for this data source.")

    # Concurrent sync prevention with stale-lock detection.
    # A sync log stuck in "running" (process crash, OOM kill, etc.) would
    # otherwise block all subsequent syncs forever. Any lock older than
    # SYNC_LOCK_TIMEOUT_MINUTES is considered stale and automatically
    # marked as failed so the user can retry without manual DB edits.
    _SYNC_LOCK_TIMEOUT_MINUTES = 30
    running_result = await session.execute(
        select(MetadataSyncLog).where(
            MetadataSyncLog.data_source_id == ds_id,
            MetadataSyncLog.status == "running",
        )
    )
    running_log = running_result.scalar_one_or_none()
    if running_log is not None:
        stale_since = (datetime.now() - running_log.started_at.replace(tzinfo=None)).total_seconds() / 60
        if stale_since < _SYNC_LOCK_TIMEOUT_MINUTES:
            raise HTTPException(status_code=409, detail="A sync is already in progress for this data source")
        # Stale lock → auto-resolve as failed and let this sync proceed
        running_log.status = "failed"
        running_log.finished_at = datetime.now()
        running_log.error_message = f"[后端] 上次同步超时（已运行 {stale_since:.0f} 分钟）"
        await session.commit()
        logger.warning(
            "Cleared stale sync lock for ds=%s (was running for %.0f min, threshold %d min)",
            ds_id, stale_since, _SYNC_LOCK_TIMEOUT_MINUTES,
        )

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

            logger.info(
                "Sync extraction: %d tables, %d columns, %d indexes, %d fks",
                len(current.get("tables", [])),
                len(current.get("columns", [])),
                len(current.get("indexes", [])),
                len(current.get("foreign_keys", [])),
            )

            # Build stored metadata from DB
            stored_tables = await _build_stored_metadata(datasource_id, session)
            logger.info("Stored metadata: %d tables, %d columns", len(stored_tables.get("tables", [])), len(stored_tables.get("columns", [])))

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
            logger.info(
                "Diff: %d changes (%d table_added, %d column_added)",
                len(changes),
                sum(1 for c in changes if c["change_type"] == "table_added"),
                sum(1 for c in changes if c["change_type"] == "column_added"),
            )
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

            # L0 staleness refresh: update semantic_description for comment-sourced fields
            await _refresh_l0_descriptions(session, changes, datasource_id)

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
            error_msg = f"[后端] {_humanize_error(e)}"
            try:
                result = await session.execute(
                    select(MetadataSyncLog).where(MetadataSyncLog.id == sync_log_id)
                )
                log = result.scalar_one_or_none()
                if log is not None:
                    log.status = "failed"
                    log.finished_at = datetime.now()
                    log.error_message = error_msg
                    await session.commit()
            except Exception:
                pass
            logger.exception("Manual sync failed for datasource %s", datasource_id)
        finally:
            _connection_manager.dispose_sync(ds_config["id"])


async def _refresh_l0_descriptions(
    session: AsyncSession,
    changes: list[dict],
    datasource_id: uuid.UUID,
) -> None:
    """Refresh semantic_description for comment-sourced fields after sync.

    Only updates fields where description_source = "schema_comment".
    Does not trigger L1/L2 rerun.
    """
    # Collect tables/columns that had comment changes
    comment_changed_tables: set[str] = set()
    comment_changed_cols: dict[str, str] = {}  # col_key -> new_comment

    for ch in changes:
        if ch["change_type"] == "column_modified":
            after = ch.get("after_value") or {}
            before = ch.get("before_value") or {}
            if after.get("column_comment") != before.get("column_comment"):
                key = f"{ch['schema_name']}.{ch['table_name']}.{ch['object_name']}"
                comment_changed_cols[key] = after.get("column_comment")
        elif ch["change_type"] == "table_modified":
            after = ch.get("after_value") or {}
            before = ch.get("before_value") or {}
            if after.get("table_comment") != before.get("table_comment"):
                comment_changed_tables.add(f"{ch['schema_name']}.{ch['table_name']}")

    if not comment_changed_tables and not comment_changed_cols:
        return

    # Refresh table-level descriptions
    if comment_changed_tables:
        tables_result = await session.execute(
            select(MetadataTable).where(
                MetadataTable.data_source_id == datasource_id,
                MetadataTable.description_source == "schema_comment",
            )
        )
        for table in tables_result.scalars().all():
            table_key = f"{table.schema_name}.{table.table_name}"
            if table_key in comment_changed_tables:
                table.semantic_description = table.table_comment

    # Refresh column-level descriptions
    if comment_changed_cols:
        cols_result = await session.execute(
            select(MetadataColumn, MetadataTable.schema_name, MetadataTable.table_name)
            .join(MetadataTable, MetadataColumn.table_id == MetadataTable.id)
            .where(
                MetadataTable.data_source_id == datasource_id,
                MetadataColumn.description_source == "schema_comment",
            )
        )
        for row in cols_result.all():
            col = row[0]
            schema_name = row[1]
            table_name = row[2]
            key = f"{schema_name}.{table_name}.{col.column_name}"
            if key in comment_changed_cols:
                col.semantic_description = comment_changed_cols[key]

    await session.commit()


async def _build_stored_metadata(datasource_id: uuid.UUID, session) -> dict:
    """Build stored metadata dict from DB for diff comparison."""
    tables_result = await session.execute(select(MetadataTable).where(MetadataTable.data_source_id == datasource_id))
    tables = tables_result.scalars().all()

    stored_tables = []
    stored_columns = []
    stored_indexes = []
    stored_fks = []

    for t in tables:
        stored_tables.append(
            {
                "table_schema": t.schema_name,
                "table_name": t.table_name,
                "table_comment": t.table_comment,
            }
        )
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
                    "column_comment": c.column_comment,
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
    """Apply diff changes to metadata tables, columns, indexes, and FKs."""

    # Pass 1: apply table changes & build schema/name → id map
    table_map: dict[tuple[str, str], uuid.UUID] = {}

    # Pre-load existing tables for lookup
    existing = await session.execute(
        select(MetadataTable).where(MetadataTable.data_source_id == datasource_id)
    )
    for t in existing.scalars().all():
        table_map[(t.schema_name, t.table_name)] = t.id

    for ch in changes:
        if ch["change_type"] == "table_added":
            tid = uuid.uuid4()
            session.add(
                MetadataTable(
                    id=tid,
                    data_source_id=datasource_id,
                    schema_name=ch["schema_name"],
                    table_name=ch["table_name"],
                    table_type=ch.get("after_value", {}).get("table_type", "BASE TABLE") if isinstance(ch.get("after_value"), dict) else "BASE TABLE",
                    table_comment=(ch.get("after_value") or {}).get("table_comment") if isinstance(ch.get("after_value"), dict) else None,
                )
            )
            table_map[(ch["schema_name"], ch["table_name"])] = tid
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
                table_map.pop((ch["schema_name"], ch["table_name"]), None)
                await session.delete(table)

    await session.flush()  # ensure table IDs are available for column FK

    # Pass 2: apply column, index, FK changes
    for ch in changes:
        table_key = (ch["schema_name"], ch["table_name"])
        tid = table_map.get(table_key)
        if tid is None:
            continue

        ctype = ch["change_type"]
        if ctype == "column_added":
            cv = ch.get("after_value") or {}
            session.add(
                MetadataColumn(
                    id=uuid.uuid4(),
                    table_id=tid,
                    column_name=ch["object_name"],
                    data_type=cv.get("data_type", ""),
                    is_nullable=cv.get("is_nullable", "YES") == "YES",
                    default_value=cv.get("column_default"),
                    column_comment=cv.get("column_comment"),
                    is_primary_key=cv.get("is_primary_key", False),
                    ordinal_position=cv.get("ordinal_position", 0),
                )
            )
        elif ctype == "column_removed":
            result = await session.execute(
                select(MetadataColumn).where(
                    MetadataColumn.table_id == tid,
                    MetadataColumn.column_name == ch["object_name"],
                )
            )
            col = result.scalar_one_or_none()
            if col is not None:
                await session.delete(col)
        elif ctype == "column_modified":
            result = await session.execute(
                select(MetadataColumn).where(
                    MetadataColumn.table_id == tid,
                    MetadataColumn.column_name == ch["object_name"],
                )
            )
            col = result.scalar_one_or_none()
            if col is not None:
                nv = ch.get("after_value") or {}
                if "data_type" in nv:
                    col.data_type = nv["data_type"]
                if "is_nullable" in nv:
                    col.is_nullable = nv["is_nullable"] == "YES"
                if "column_comment" in nv:
                    col.column_comment = nv["column_comment"]

    await session.commit()


# ── Learning ────────────────────────────────────────────────────


async def _run_learning_auto(datasource_id: uuid.UUID) -> None:
    """Run learning pipeline automatically after metadata extraction.

    Includes mutex check: skips if a sync is running.
    """
    from config.database import get_session as _get_session
    from learning.orchestrator import run_learning

    async for session in _get_session():
        # Mutex: skip if a sync is running
        running_sync = await session.execute(
            select(MetadataSyncLog).where(
                MetadataSyncLog.data_source_id == datasource_id,
                MetadataSyncLog.status == "running",
            )
        )
        if running_sync.scalar_one_or_none() is not None:
            return

        try:
            await run_learning(session, datasource_id, trigger_type="auto")
        except Exception:
            logger.exception("Auto-learning failed for datasource %s", datasource_id)


@router.post("/{ds_id}/learn", status_code=202)
async def trigger_learn(ds_id: uuid.UUID, session: SessionDep) -> LearnResponse:
    await _get_ds_or_404(ds_id, session)

    # Mutex: reject if a sync is running
    from fastapi import HTTPException

    running_sync = await session.execute(
        select(MetadataSyncLog).where(
            MetadataSyncLog.data_source_id == ds_id,
            MetadataSyncLog.status == "running",
        )
    )
    if running_sync.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="A sync task is already running for this data source.")

    # Run learning synchronously within the request session for Issue 001
    # (L0 only, no background task needed since it's fast)
    from learning.orchestrator import run_learning

    try:
        learning_log_id = await run_learning(session, ds_id, trigger_type="manual")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"[后端] {_humanize_error(e)}")

    return LearnResponse(
        learning_log_id=learning_log_id,
        message="Learning completed",
    )


@router.get("/{ds_id}/learning-logs")
async def get_learning_logs(ds_id: uuid.UUID, session: SessionDep) -> list[LearningLogResponse]:
    await _get_ds_or_404(ds_id, session)
    result = await session.execute(
        select(MetadataLearningLog)
        .where(MetadataLearningLog.data_source_id == ds_id)
        .order_by(MetadataLearningLog.started_at.desc())
    )
    logs = result.scalars().all()
    return [LearningLogResponse.model_validate(log) for log in logs]


# ── Knowledge-base refresh ────────────────────────────────────────


@router.post("/{ds_id}/refresh-knowledge", status_code=202)
async def refresh_knowledge(ds_id: uuid.UUID, session: SessionDep) -> dict:
    """Rebuild vector index + graph for a data source without re-running learning."""
    await _get_ds_or_404(ds_id, session)

    # Run synchronously so the caller sees success/failure immediately
    from knowledge.embedding import EmbeddingClient
    from knowledge.graph_store import GraphStore
    from knowledge.lifecycle import refresh_knowledge_base
    from knowledge.vector_store import VectorStore

    try:
        await refresh_knowledge_base(
            session,
            ds_id,
            vector_store=VectorStore(),
            graph_store=GraphStore(),
            embedding_client=EmbeddingClient(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"[后端] 知识库刷新失败: {_humanize_error(e)}")

    return {"message": "Knowledge base refreshed"}
