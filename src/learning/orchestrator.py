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
    FieldSignal,
    LLMCaller,
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
    """Run the full learning pipeline (L0 → L1 → L2).

    L0 copies schema comments into ``semantic_description``. L1 does field-name
    splitting (writes ``semantic_description``), data-pattern detection (writes
    structural stats only), and value-overlap foreign-key inference (writes
    ``metadata_inferred_fks``). L2 does LLM semantic inference. Coverage is
    computed from non-null ``semantic_description`` columns. Each stage's
    failure is suppressed so it does not block the rest of the pipeline.
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

        # L1: pattern detection writes structural stats (enum/null_ratio/
        # numeric_range) to columns; it does NOT write semantic_description
        # and must not count toward coverage. Failure is suppressed.
        with contextlib.suppress(Exception):
            await _run_pattern_detection_with_ds(session, data_source_id)

        # L1: value-overlap FK inference (writes metadata_inferred_fks,
        # recompute-replace). Does not affect semantic coverage. Suppressed.
        with contextlib.suppress(Exception):
            await _run_fk_inference_with_ds(session, data_source_id)

        # l1_count = splitting only (the only L1 step that writes
        # semantic_description). Pattern detection is intentionally excluded.
        l1_count = l1_split_count

        # L2: LLM semantic inference
        l2_count = 0
        l2_llm_calls = 0
        with contextlib.suppress(Exception):
            l2_result = await _run_l2_with_ds(session, data_source_id)
            l2_count = l2_result[0]
            l2_llm_calls = l2_result[1]

        # Coverage = columns with a non-null semantic_description, counted
        # directly from the DB. This fixes the prior bug where pattern
        # detection (writing null_ratio to ~every column) inflated the count
        # via l0+l1+l2 summation, pushing the ratio to ~100% or beyond.
        from sqlalchemy import func

        covered_result = await session.execute(
            select(func.count())
            .where(MetadataColumn.table_id.in_(table_ids))
            .where(MetadataColumn.semantic_description.is_not(None))
        )
        columns_described = covered_result.scalar() or 0

        # Determine status (avoid division by zero for empty data sources).
        if total_columns == 0:
            status = "failed"
        elif columns_described / total_columns >= 0.8:
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


async def _run_fk_inference_with_ds(
    session: AsyncSession,
    data_source_id: uuid.UUID,
) -> int:
    """Look up the DataSource, create a connection, and run FK inference.

    Returns 0 if the DataSource is not found, inactive, or connection fails.
    """
    from sqlalchemy import text

    from config.data_source_model import DataSource
    from config.encryption import decrypt_value
    from config.settings import Settings
    from db.connection import ConnectionManager
    from learning.fk_inference import run_fk_inference

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

    async def query_executor(sql: str) -> Any:
        async with engine.connect() as conn:
            result = await conn.execute(text(sql))
            # Row-count estimate queries return a single aggregate row; distinct
            # value queries return a list of scalars.
            upper = sql.lstrip().upper()
            if upper.startswith("EXPLAIN") or upper.startswith("SELECT C.RELTUPLES"):
                return dict(result.mappings().one())
            return result.scalars().all()

    try:
        return await run_fk_inference(
            session,
            data_source_id,
            query_executor=query_executor,
            engine_type=ds.engine,
        )
    finally:
        await engine.dispose()


async def run_l2_inference(
    session_factory: Callable[[], AsyncSession],
    data_source_id: uuid.UUID,
    *,
    llm_caller: LLMCaller,
    max_concurrency: int | None = None,
    timeout_minutes: int | None = None,
    max_calls: int | None = None,
) -> tuple[int, int]:
    """Run L2 LLM inference for tables with uncovered fields.

    Each concurrent task opens its own :class:`AsyncSession` from
    *session_factory* — ``AsyncSession`` is not safe for concurrent use across
    tasks, so a session is never shared by more than one task.

    L2 infers descriptions from **structured signals only** (field name, data
    type, L1 enum values, L0 comment, splitting result). No raw business-data
    rows are sent to the LLM.

    Returns ``(l2_count, l2_llm_calls)`` — the number of newly described
    columns and the total LLM API calls made.
    """
    from datetime import datetime as _dt

    from config.settings import Settings

    if max_concurrency is None or timeout_minutes is None or max_calls is None:
        settings = Settings()
        if max_concurrency is None:
            max_concurrency = settings.learning_l2_max_concurrency
        if timeout_minutes is None:
            timeout_minutes = settings.learning_job_timeout_minutes
        if max_calls is None:
            max_calls = settings.learning_l2_max_calls

    # Discover tables with a short-lived session; each is then processed in its own.
    async with session_factory() as session:
        tables_result = await session.execute(
            select(MetadataTable).where(MetadataTable.data_source_id == data_source_id)
        )
        tables = tables_result.scalars().all()

    l2_count = 0
    l2_llm_calls = 0
    semaphore = asyncio.Semaphore(max_concurrency)
    start_time = _dt.now()
    timeout_seconds = timeout_minutes * 60
    # Shared call counter. asyncio is single-threaded, so the cap check and the
    # increment below run without an await between them → atomic w.r.t. other tasks.
    counter = {"calls": 0}

    async def _process_table(table: MetadataTable) -> tuple[int, int]:
        """Process a single table: build structured signals → LLM → write."""
        async with semaphore:
            # Overall timeout guard
            elapsed = (_dt.now() - start_time).total_seconds()
            if elapsed >= timeout_seconds:
                return 0, 0

            async with session_factory() as session:
                cols_result = await session.execute(select(MetadataColumn).where(MetadataColumn.table_id == table.id))
                columns = cols_result.scalars().all()

                uncovered = [c for c in columns if c.semantic_description is None]
                if not uncovered:
                    return 0, 0

                # Cost cap: stop issuing new LLM calls once the limit is hit.
                if max_calls and counter["calls"] >= max_calls:
                    logger.info(
                        "L2 reached max_calls=%d before table %s; skipping",
                        max_calls,
                        table.table_name,
                    )
                    return 0, 0
                counter["calls"] += 1

                signals = [
                    FieldSignal(
                        name=c.column_name,
                        data_type=c.data_type,
                        enum_values=c.detected_enum_values,
                        comment=c.column_comment,
                        split=split_field_name(c.column_name),
                    )
                    for c in uncovered
                ]

                result = await call_llm_with_retry(llm_caller, table.table_name, signals)

                if result is None:
                    return 0, 1

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

                await session.commit()
                return described, 1

    tasks = [_process_table(table) for table in tables]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, Exception):
            logger.error("L2 table processing error: %s", r)
            continue
        l2_count += r[0]
        l2_llm_calls += r[1]

    if max_calls and counter["calls"] >= max_calls:
        logger.info(
            "L2 stopped early after %d LLM calls (max_calls=%d)",
            counter["calls"],
            max_calls,
        )

    return l2_count, l2_llm_calls


async def _run_l2_with_ds(
    session: AsyncSession,
    data_source_id: uuid.UUID,
) -> tuple[int, int]:
    """Verify the data source is active and run L2 inference.

    L2 needs no access to the target (business) database — it works only from
    already-extracted metadata. Returns ``(0, 0)`` if the data source is not
    found or inactive.
    """
    from config.data_source_model import DataSource
    from config.database import get_session_factory
    from config.settings import Settings
    from llm.client import create_llm_caller

    ds_result = await session.execute(select(DataSource).where(DataSource.id == data_source_id))
    ds = ds_result.scalar_one_or_none()
    if ds is None or not ds.is_active:
        return 0, 0

    settings = Settings()
    llm_caller = create_llm_caller(settings)
    session_factory = get_session_factory()

    return await run_l2_inference(
        session_factory,
        data_source_id,
        llm_caller=llm_caller,
    )
