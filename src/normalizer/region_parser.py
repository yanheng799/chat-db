"""Region/place-name normalizer — granularity-adaptive + hierarchy expansion. (issue #26)"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from normalizer.mapping_service import list_regions
from normalizer.types import NormalizedValue

logger = logging.getLogger(__name__)


async def normalize_region(
    session: AsyncSession,
    raw_value: str,
    data_source_id: Any,
) -> NormalizedValue:
    text = raw_value.strip()
    regions = await list_regions(session, data_source_id)

    # match by name or alias
    match = None
    for r in regions:
        if r["name"] == text or text in (r.get("aliases") or []):
            match = r
            break

    if match is None:
        return NormalizedValue(original=raw_value, value_type="region", need_confirm=True)

    descendants = _collect_descendants(match, regions)
    if not descendants:
        return NormalizedValue(
            original=raw_value,
            normalized=match["name"],
            value_type="region",
            db_representation=f"{match['level']} = '{match['name']}'",
            confidence=1.0,
            matched_by="name",
        )
    names = sorted({match["name"]} | {d["name"] for d in descendants})
    in_list = ", ".join(f"'{n}'" for n in names)
    return NormalizedValue(
        original=raw_value,
        normalized=names,
        value_type="region",
        db_representation=f"{match['level']} IN ({in_list})",
        confidence=1.0,
        matched_by="name",
    )


def _collect_descendants(match: dict, all_regions: list[dict]) -> list[dict]:
    """Collect all descendants of *match* (children, grandchildren, ...)."""
    code = match["code"]
    result = []
    for r in all_regions:
        if r.get("parent_code") == code:
            result.append(r)
            result.extend(_collect_descendants(r, all_regions))
    return result
