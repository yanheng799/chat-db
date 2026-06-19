"""Fuzzy quantifier detector — need_confirm, never auto-quantify. (issue #28)"""

from __future__ import annotations

import logging
from normalizer.types import NormalizedValue

logger = logging.getLogger(__name__)

_QUANTIFIERS: set[str] = {"高价值", "大额", "小额", "适中", "大量", "少量"}


def detect_quantifier(raw_value: str) -> NormalizedValue:
    """Check for fuzzy quantifiers; return ``need_confirm=True`` if detected.

    Never auto-quantifies — Phase 6 asks the user for a concrete threshold.
    """
    text = raw_value.strip()
    for q in _QUANTIFIERS:
        if q in text:
            return NormalizedValue(
                original=raw_value,
                value_type="quantifier",
                need_confirm=True,
            )
    return NormalizedValue(original=raw_value, value_type="quantifier")
