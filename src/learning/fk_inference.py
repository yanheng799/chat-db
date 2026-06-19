"""L1 value-overlap foreign-key inference.

Infers undeclared foreign-key relationships by:

1. Generating candidate column pairs across tables — data-type match, the
   referenced (target) side is a primary key or unique column, and the source
   column's name similarity to the target meets a threshold.
2. Computing the value-overlap rate of each candidate against the live data
   source (reusing the shared ``query_executor`` and the
   :func:`~learning.pattern_detector.should_use_sampling` decision).
3. Emitting an :class:`~metadata.models.MetadataInferredForeignKey` row when
   the overlap rate meets the threshold, with confidence mapped from the
   overlap rate and ``source='rule_inference'``.

Inferred FKs are recomputed and replaced on every learning run.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from learning.pattern_detector import compute_table_estimated_rows, should_use_sampling
from metadata.models import (
    MetadataColumn,
    MetadataIndex,
    MetadataInferredForeignKey,
    MetadataTable,
)

logger = logging.getLogger(__name__)

QueryExecutor = Callable[[str], Awaitable[object]]

DEFAULT_OVERLAP_THRESHOLD = 0.8
DEFAULT_NAME_SIMILARITY_THRESHOLD = 0.5
# Cap on distinct values inspected per column — bounds memory and query time
# for large tables (a bounded scan serves as the sample).
DISTINCT_VALUE_CAP = 10_000


# ---------------------------------------------------------------------------
# Pure scoring helpers
# ---------------------------------------------------------------------------


def _normalize_type(data_type: str) -> str:
    """Normalize a SQL type for matching (lowercase, strip length)."""
    return data_type.lower().split("(")[0].strip()


def compute_name_similarity(source_column: str, target_column: str, target_table: str) -> float:
    """Name similarity between a source column and a referenced (table, column).

    A FK column frequently echoes the referenced table's name (e.g.
    ``customer_id`` → ``customers``), so we take the max of the column↔column
    and column↔table :class:`~difflib.SequenceMatcher` ratios.
    """
    src = source_column.lower()
    col_ratio = SequenceMatcher(None, src, target_column.lower()).ratio()
    table_ratio = SequenceMatcher(None, src, target_table.lower()).ratio()
    return max(col_ratio, table_ratio)


def compute_overlap_rate(source_values: set, target_values: set) -> float:
    """Containment of the source value set in the target value set.

    For a valid FK every source value exists in the referenced column, so a
    high containment (intersection / source distinct) is a strong FK signal.
    Returns 0.0 when the source has no values.
    """
    if not source_values:
        return 0.0
    return len(source_values & target_values) / len(source_values)


def confidence_for_overlap(overlap_rate: float) -> float | None:
    """Map an overlap rate to a confidence, or ``None`` if not inferable.

    ``overlap >= 0.95 → 0.8``; ``0.8 <= overlap < 0.95 → 0.65``; else ``None``.
    """
    if overlap_rate >= 0.95:
        return 0.8
    if overlap_rate >= 0.8:
        return 0.65
    return None


# ---------------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------------


@dataclass
class _Candidate:
    source_table: MetadataTable
    source_column: MetadataColumn
    target_table: MetadataTable
    target_column: MetadataColumn
    name_similarity: float


def _unique_column_names(indexes: list[MetadataIndex]) -> set[str]:
    """Single-column names covered by a single-column unique index."""
    names: set[str] = set()
    for idx in indexes:
        if idx.is_unique and len(idx.column_names) == 1:
            names.add(idx.column_names[0])
    return names


def generate_candidates(
    tables: list[MetadataTable],
    columns_by_table: dict[uuid.UUID, list[MetadataColumn]],
    indexes_by_table: dict[uuid.UUID, list[MetadataIndex]],
    name_similarity_threshold: float = DEFAULT_NAME_SIMILARITY_THRESHOLD,
) -> list[_Candidate]:
    """Build candidate FK pairs meeting type-match + referenced-side uniqueness + name similarity."""
    candidates: list[_Candidate] = []
    for source_table in tables:
        source_cols = columns_by_table.get(source_table.id, [])
        for target_table in tables:
            if target_table.id == source_table.id:
                continue
            target_cols = columns_by_table.get(target_table.id, [])
            target_unique = _unique_column_names(indexes_by_table.get(target_table.id, []))
            referenced = [c for c in target_cols if c.is_primary_key or c.column_name in target_unique]
            for source_col in source_cols:
                source_type = _normalize_type(source_col.data_type)
                for target_col in referenced:
                    if _normalize_type(target_col.data_type) != source_type:
                        continue
                    similarity = compute_name_similarity(
                        source_col.column_name, target_col.column_name, target_table.table_name
                    )
                    if similarity >= name_similarity_threshold:
                        candidates.append(
                            _Candidate(
                                source_table=source_table,
                                source_column=source_col,
                                target_table=target_table,
                                target_column=target_col,
                                name_similarity=similarity,
                            )
                        )
    return candidates


# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------


def build_distinct_values_query(
    table_name: str,
    schema_name: str | None,
    column_name: str,
    engine_type: str,
    use_sampling: bool,
) -> str:
    """Build a ``SELECT DISTINCT`` query capped at :data:`DISTINCT_VALUE_CAP`.

    For PostgreSQL large tables, ``TABLESAMPLE SYSTEM (1)`` is used (per the
    :func:`should_use_sampling` decision); MySQL relies on the ``LIMIT`` cap.
    """
    if engine_type == "postgresql":
        fqn = f'"{schema_name}"."{table_name}"' if schema_name else f'"{table_name}"'
        sample = " TABLESAMPLE SYSTEM (1)" if use_sampling else ""
        return f'SELECT DISTINCT "{column_name}" FROM {fqn}{sample} LIMIT {DISTINCT_VALUE_CAP}'
    fqn = f"`{table_name}`"
    return f"SELECT DISTINCT `{column_name}` FROM {fqn} LIMIT {DISTINCT_VALUE_CAP}"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _is_estimate_query(sql: str) -> bool:
    stripped = sql.lstrip().upper()
    return stripped.startswith("EXPLAIN") or stripped.startswith("SELECT C.RELTUPLES")


async def run_fk_inference(
    session: AsyncSession,
    data_source_id: uuid.UUID,
    *,
    query_executor: QueryExecutor,
    engine_type: str = "postgresql",
    overlap_threshold: float = DEFAULT_OVERLAP_THRESHOLD,
    name_similarity_threshold: float = DEFAULT_NAME_SIMILARITY_THRESHOLD,
) -> int:
    """Infer foreign keys for a data source and persist them.

    Existing inferred FKs for the data source are replaced (recompute-and-
    replace). Returns the number of inferred FK rows written.
    """
    tables_result = await session.execute(select(MetadataTable).where(MetadataTable.data_source_id == data_source_id))
    tables = tables_result.scalars().all()
    if not tables:
        return 0

    table_ids = [t.id for t in tables]

    cols_result = await session.execute(select(MetadataColumn).where(MetadataColumn.table_id.in_(table_ids)))
    columns_by_table: dict[uuid.UUID, list[MetadataColumn]] = {}
    for col in cols_result.scalars().all():
        columns_by_table.setdefault(col.table_id, []).append(col)

    idx_result = await session.execute(select(MetadataIndex).where(MetadataIndex.table_id.in_(table_ids)))
    indexes_by_table: dict[uuid.UUID, list[MetadataIndex]] = {}
    for idx in idx_result.scalars().all():
        indexes_by_table.setdefault(idx.table_id, []).append(idx)

    candidates = generate_candidates(tables, columns_by_table, indexes_by_table, name_similarity_threshold)

    # Recompute-and-replace: clear existing inferred FKs for this data source.
    await session.execute(
        MetadataInferredForeignKey.__table__.delete().where(MetadataInferredForeignKey.data_source_id == data_source_id)
    )
    await session.flush()

    estimated_rows_cache: dict[uuid.UUID, int] = {}

    async def _estimated_rows(table: MetadataTable) -> int:
        if table.id in estimated_rows_cache:
            return estimated_rows_cache[table.id]
        try:
            row = await query_executor(compute_table_estimated_rows(table.table_name, table.schema_name, engine_type))
            estimate = row.get("estimate", 0) or 0 if isinstance(row, dict) else 0
        except Exception:
            estimate = 0
        estimated_rows_cache[table.id] = estimate
        return estimate

    inferred_count = 0
    for candidate in candidates:
        use_sampling = should_use_sampling(await _estimated_rows(candidate.source_table))

        try:
            src_raw = await query_executor(
                build_distinct_values_query(
                    candidate.source_table.table_name,
                    candidate.source_table.schema_name,
                    candidate.source_column.column_name,
                    engine_type,
                    use_sampling,
                )
            )
            tgt_raw = await query_executor(
                build_distinct_values_query(
                    candidate.target_table.table_name,
                    candidate.target_table.schema_name,
                    candidate.target_column.column_name,
                    engine_type,
                    use_sampling,
                )
            )
        except Exception as e:
            logger.warning(
                "FK overlap query failed for %s.%s -> %s.%s: %s",
                candidate.source_table.table_name,
                candidate.source_column.column_name,
                candidate.target_table.table_name,
                candidate.target_column.column_name,
                e,
            )
            continue

        source_values = {v for v in src_raw if v is not None} if isinstance(src_raw, (list, tuple)) else set()
        target_values = {v for v in tgt_raw if v is not None} if isinstance(tgt_raw, (list, tuple)) else set()

        overlap = compute_overlap_rate(source_values, target_values)
        if overlap < overlap_threshold:
            continue
        confidence = confidence_for_overlap(overlap)
        if confidence is None:
            continue

        session.add(
            MetadataInferredForeignKey(
                data_source_id=data_source_id,
                source_schema=candidate.source_table.schema_name,
                source_table=candidate.source_table.table_name,
                source_column=candidate.source_column.column_name,
                target_schema=candidate.target_table.schema_name,
                target_table=candidate.target_table.table_name,
                target_column=candidate.target_column.column_name,
                overlap_rate=overlap,
                name_similarity=candidate.name_similarity,
                confidence=confidence,
                source="rule_inference",
            )
        )
        inferred_count += 1

    await session.commit()
    return inferred_count
