"""Learning orchestrator — coordinates L0/L1/L2 learning pipeline."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metadata.models import MetadataColumn, MetadataLearningLog, MetadataTable


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

        # L1 placeholder — Issue 002 will implement
        l1_count = 0

        # L2 placeholder — Issue 003 will implement
        l2_count = 0

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
        learning_log.l2_llm_calls = 0
        await session.commit()

    except Exception as e:
        learning_log.status = "failed"
        learning_log.finished_at = datetime.now()
        learning_log.error_message = str(e)
        await session.commit()

    return learning_log_id
