"""Learning orchestrator — coordinates L0/L1/L2 learning pipeline."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from learning.l2_inference import (
    LLMCaller,
    build_sample_query,
    call_llm_with_retry,
)
from learning.pattern_detector import (
    build_aggregate_query,
    compute_table_estimated_rows,
    detect_enum_fields,
    is_numeric_type,
    parse_aggregate_results,
    should_use_sampling,
)
from learning.splitter import split_field_name
from metadata.models import MetadataColumn, MetadataLearningLog, MetadataTable

logger = logging.getLogger(__name__)

# Type alias for the injected query executor
QueryExecutor = Callable[[str], Awaitable[dict[str, Any]]]


async def run_l0(session: AsyncSession, data_source_id: uuid.UUID) -> int:
    """Run L0: copy existing comments to semantic_description.

    Returns the count of columns covered by L0.
    """
    # Process tables
    tables_result = await session.execute(select(MetadataTable).where(MetadataTable.data_source_id == data_source_id))
    tables = tables_result.scalars().all()

    for table in tables:
        if table.table_comment and not table.semantic_description:
            table.semantic_description = table.table_comment
            table.description_source = "schema_comment"
            table.description_confidence = 1.0

    # Process columns
    table_ids = [t.id for t in tables]
    if not table_ids:
        await session.commit()
        return 0

    columns_result = await session.execute(select(MetadataColumn).where(MetadataColumn.table_id.in_(table_ids)))
    columns = columns_result.scalars().all()

    l0_count = 0
    for col in columns:
        if col.column_comment and not col.semantic_description:
            col.semantic_description = col.column_comment
            col.description_source = "schema_comment"
            col.description_confidence = 1.0
            l0_count += 1

    await session.commit()
    return l0_count


async def run_l1_splitting(session: AsyncSession, data_source_id: uuid.UUID) -> int:
    """Run L1 field-name splitting for columns not yet annotated by L0.

    Only columns where ``semantic_description`` is still ``None`` are
    processed.  If :func:`split_field_name` succeeds the column receives
    ``description_source="rule_inference"`` and
    ``description_confidence=0.7``; otherwise it is left untouched for L2.

    Returns the count of newly described columns.
    """
    tables_result = await session.execute(select(MetadataTable).where(MetadataTable.data_source_id == data_source_id))
    tables = tables_result.scalars().all()
    table_ids = [t.id for t in tables]
    if not table_ids:
        return 0

    columns_result = await session.execute(select(MetadataColumn).where(MetadataColumn.table_id.in_(table_ids)))
    columns = columns_result.scalars().all()

    l1_count = 0
    for col in columns:
        # Skip columns already annotated by L0 (or any earlier pass)
        if col.semantic_description is not None:
            continue

        translated = split_field_name(col.column_name)
        if translated is not None:
            col.semantic_description = translated
            col.description_source = "rule_inference"
            col.description_confidence = 0.7
            l1_count += 1

    await session.commit()
    return l1_count


async def run_l1_pattern_detection(
    session: AsyncSession,
    data_source_id: uuid.UUID,
    *,
    query_executor: QueryExecutor,
    engine_type: str = "postgresql",
) -> int:
    """Run L1 data pattern detection for all tables in a data source.

    Connects to the user's data source (via *query_executor*), runs one
    aggregate query per table, and updates every
    :class:`MetadataColumn` with:

    - ``detected_enum_values`` — when the column is a low-cardinality enum
    - ``null_ratio`` — ``null_count / total_rows``
    - ``numeric_range`` — ``{min, max}`` for numeric columns only

    Pattern detection runs on **all** columns regardless of whether they
    already have a ``semantic_description`` (the skip-only rule only
    applies to name splitting).

    Returns the total number of columns where at least one pattern field
    was written.
    """
    tables_result = await session.execute(select(MetadataTable).where(MetadataTable.data_source_id == data_source_id))
    tables = tables_result.scalars().all()
    if not tables:
        return 0

    total_updated = 0

    for table in tables:
        # Fetch columns for this table
        cols_result = await session.execute(select(MetadataColumn).where(MetadataColumn.table_id == table.id))
        columns = cols_result.scalars().all()
        if not columns:
            continue

        # Estimate row count to decide on sampling
        est_sql = compute_table_estimated_rows(table.table_name, table.schema_name, engine_type)
        est_row = await query_executor(est_sql)
        estimated_rows = est_row.get("estimate", 0) or 0

        # Build and execute aggregate query
        use_sampling = should_use_sampling(estimated_rows)
        agg_sql = build_aggregate_query(
            table_name=table.table_name,
            schema_name=table.schema_name,
            columns=columns,
            engine_type=engine_type,
            use_sampling=use_sampling,
        )
        agg_row = await query_executor(agg_sql)

        # Parse results
        parsed = parse_aggregate_results(agg_row, columns)
        total_rows = parsed.pop("__total_rows__", 0)

        # Apply total_rows from system stats when sampling (not from sample)
        if use_sampling and estimated_rows > 0:
            total_rows = estimated_rows

        # Detect enums
        column_stats = {cn: {"distinct_count": v["distinct_count"]} for cn, v in parsed.items()}
        enum_map = detect_enum_fields(total_rows, column_stats)

        # Write results to each column
        col_by_name = {c.column_name: c for c in columns}
        for col_name, stats in parsed.items():
            col = col_by_name.get(col_name)
            if col is None:
                continue

            updated = False

            # Enum values
            if enum_map.get(col_name):
                values = stats.get("values")
                if values:
                    col.detected_enum_values = values
                    updated = True

            # Null ratio
            if total_rows > 0:
                null_ratio = (stats.get("null_count", 0) or 0) / total_rows
                col.null_ratio = null_ratio
                updated = True

            # Numeric range
            if is_numeric_type(col.data_type) and "min" in stats and "max" in stats:
                min_val = stats["min"]
                max_val = stats["max"]
                if min_val is not None and max_val is not None:
                    col.numeric_range = {"min": min_val, "max": max_val}
                    updated = True

            if updated:
                total_updated += 1

    await session.commit()
    return total_updated


async def run_learning(
    session: AsyncSession,
    data_source_id: uuid.UUID,
    trigger_type: str = "auto",
) -> uuid.UUID:
    """Run the full learning pipeline (L0 → L1 placeholder → L2 placeholder).

    Creates a learning log entry and runs L0.
    L1 and L2 are placeholders for now (Issues 002 and 003).
    """
    learning_log_id = uuid.uuid4()
    learning_log = MetadataLearningLog(
        id=learning_log_id,
        data_source_id=data_source_id,
        trigger_type=trigger_type,
        status="running",
        started_at=datetime.now(),
    )
    session.add(learning_log)
    await session.commit()

    try:
        # Count total tables and columns
        tables_result = await session.execute(
            select(MetadataTable).where(MetadataTable.data_source_id == data_source_id)
        )
        tables = tables_result.scalars().all()
        table_ids = [t.id for t in tables]

        total_columns = 0
        if table_ids:
            from sqlalchemy import func

            count_result = await session.execute(select(func.count()).where(MetadataColumn.table_id.in_(table_ids)))
            total_columns = count_result.scalar() or 0

        # L0
        l0_count = await run_l0(session, data_source_id)

        # L1: field name splitting
        l1_split_count = await run_l1_splitting(session, data_source_id)

        # L1: pattern detection (requires data source connection)
        l1_pattern_count = 0
        with contextlib.suppress(Exception):
            # Pattern detection failure should not block the pipeline
            l1_pattern_count = await _run_pattern_detection_with_ds(session, data_source_id)

        l1_count = l1_split_count + l1_pattern_count

        # L2: LLM semantic inference
        l2_count = 0
        l2_llm_calls = 0
        with contextlib.suppress(Exception):
            l2_result = await _run_l2_with_ds(session, data_source_id)
            l2_count = l2_result[0]
            l2_llm_calls = l2_result[1]

        columns_described = l0_count + l1_count + l2_count

        # Determine status
        if total_columns == 0 or columns_described / total_columns >= 0.8:
            status = "success"
        elif columns_described > 0:
            status = "partial_success"
        else:
            status = "failed"

        learning_log.status = status
        learning_log.finished_at = datetime.now()
        learning_log.tables_processed = len(tables)
        learning_log.columns_described = columns_described
        learning_log.l0_count = l0_count
        learning_log.l1_count = l1_count
        learning_log.l2_count = l2_count
        learning_log.l2_llm_calls = l2_llm_calls
        await session.commit()

    except Exception as e:
        learning_log.status = "failed"
        learning_log.finished_at = datetime.now()
        learning_log.error_message = str(e)
        await session.commit()

    return learning_log_id


async def _run_pattern_detection_with_ds(
    session: AsyncSession,
    data_source_id: uuid.UUID,
) -> int:
    """Look up the DataSource, create a connection, and run pattern detection.

    Returns 0 if the DataSource is not found or connection fails.
    """
    from sqlalchemy import text

    from config.data_source_model import DataSource
    from config.encryption import decrypt_value
    from config.settings import Settings
    from db.connection import ConnectionManager

    ds_result = await session.execute(select(DataSource).where(DataSource.id == data_source_id))
    ds = ds_result.scalar_one_or_none()
    if ds is None or not ds.is_active:
        return 0

    settings = Settings()
    password = decrypt_value(ds.password_encrypted, settings.encryption_key)
    ds_config = {
        "engine": ds.engine,
        "host": ds.host,
        "port": ds.port,
        "username": ds.username,
        "password": password,
        "database": ds.database,
    }

    cm = ConnectionManager()
    engine = cm.create_engine(ds_config)

    async def query_executor(sql: str) -> dict[str, Any]:
        async with engine.connect() as conn:
            result = await conn.execute(text(sql))
            row = result.mappings().one()
            return dict(row)

    try:
        return await run_l1_pattern_detection(
            session,
            data_source_id,
            query_executor=query_executor,
            engine_type=ds.engine,
        )
    finally:
        await engine.dispose()


async def run_l2_inference(
    session: AsyncSession,
    data_source_id: uuid.UUID,
    *,
    query_executor: QueryExecutor,
    llm_caller: LLMCaller,
    engine_type: str = "postgresql",
    max_concurrency: int | None = None,
    timeout_minutes: int | None = None,
) -> tuple[int, int]:
    """Run L2 LLM inference for tables with uncovered fields.

    Returns ``(l2_count, l2_llm_calls)`` — the number of newly described
    columns and the total LLM API calls made.
    """
    from datetime import datetime as _dt

    from config.settings import Settings

    # Use provided values or fall back to Settings defaults
    if max_concurrency is None or timeout_minutes is None:
        settings = Settings()
        if max_concurrency is None:
            max_concurrency = settings.learning_l2_max_concurrency
        if timeout_minutes is None:
            timeout_minutes = settings.learning_job_timeout_minutes

    tables_result = await session.execute(select(MetadataTable).where(MetadataTable.data_source_id == data_source_id))
    tables = tables_result.scalars().all()

    l2_count = 0
    l2_llm_calls = 0
    semaphore = asyncio.Semaphore(max_concurrency)
    start_time = _dt.now()
    timeout_seconds = timeout_minutes * 60

    async def _process_table(table: MetadataTable) -> tuple[int, int]:
        """Process a single table: sample → LLM → write results."""
        async with semaphore:
            # Check timeout
            elapsed = (_dt.now() - start_time).total_seconds()
            if elapsed >= timeout_seconds:
                return 0, 0

            # Get columns for this table
            cols_result = await session.execute(select(MetadataColumn).where(MetadataColumn.table_id == table.id))
            columns = cols_result.scalars().all()

            # Filter to only uncovered columns
            uncovered = [c for c in columns if c.semantic_description is None]
            if not uncovered:
                return 0, 0

            field_names = [c.column_name for c in uncovered]

            # Build and execute sample query
            sample_sql = build_sample_query(table.table_name, table.schema_name, uncovered, engine_type)
            sample_rows: list[dict[str, Any]] = []
            if sample_sql:
                try:
                    rows = await query_executor(sample_sql)
                    # query_executor may return a single dict or list of dicts
                    if isinstance(rows, list):
                        sample_rows = rows
                    elif isinstance(rows, dict):
                        sample_rows = [rows]
                except Exception:
                    sample_rows = []

            # Call LLM with retry
            result = await call_llm_with_retry(llm_caller, table.table_name, field_names, sample_rows)
            llm_calls = 1

            if result is None:
                return 0, llm_calls

            # Write results
            described = 0
            col_by_name = {c.column_name: c for c in uncovered}
            for field_name, description in result.items():
                if not description or not isinstance(description, str):
                    continue
                col = col_by_name.get(field_name)
                if col is not None and col.semantic_description is None:
                    col.semantic_description = description
                    col.description_source = "llm_inference"
                    col.description_confidence = 0.5
                    described += 1

            return described, llm_calls

    # Process all tables concurrently with semaphore
    tasks = [_process_table(table) for table in tables]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, Exception):
            logger.error("L2 table processing error: %s", r)
            continue
        l2_count += r[0]
        l2_llm_calls += r[1]

    await session.commit()
    return l2_count, l2_llm_calls


async def _run_l2_with_ds(
    session: AsyncSession,
    data_source_id: uuid.UUID,
) -> tuple[int, int]:
    """Look up the DataSource, create connections, and run L2 inference.

    Returns ``(0, 0)`` if the DataSource is not found or setup fails.
    """
    from sqlalchemy import text

    from config.data_source_model import DataSource
    from config.encryption import decrypt_value
    from config.settings import Settings
    from db.connection import ConnectionManager
    from llm.client import create_llm_caller

    ds_result = await session.execute(select(DataSource).where(DataSource.id == data_source_id))
    ds = ds_result.scalar_one_or_none()
    if ds is None or not ds.is_active:
        return 0, 0

    settings = Settings()
    password = decrypt_value(ds.password_encrypted, settings.encryption_key)
    ds_config = {
        "engine": ds.engine,
        "host": ds.host,
        "port": ds.port,
        "username": ds.username,
        "password": password,
        "database": ds.database,
    }

    cm = ConnectionManager()
    engine = cm.create_engine(ds_config)

    async def query_executor(sql: str) -> Any:
        async with engine.connect() as conn:
            result = await conn.execute(text(sql))
            rows = result.mappings().all()
            if len(rows) == 1:
                return dict(rows[0])
            return [dict(r) for r in rows]

    llm_caller = create_llm_caller(settings)

    try:
        return await run_l2_inference(
            session,
            data_source_id,
            query_executor=query_executor,
            llm_caller=llm_caller,
            engine_type=ds.engine,
        )
    finally:
        await engine.dispose()
