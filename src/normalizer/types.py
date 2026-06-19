"""NormalizedValue — the structured result of value standardization (Phase 4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NormalizedValue:
    """Output of one value-standardization step.

    Consumed by Phase 6 SQL generation. When ``need_confirm`` is True the value
    was not resolvable and Phase 6 should batch-ask the user.
    """

    original: str
    """The raw user value text (e.g. ``'上个月'``)."""

    normalized: Any | None = None
    """The normalized value (e.g. a Python ``date`` range tuple)."""

    value_type: str = ""
    """One of ``time`` / ``enum`` / ``region`` / ``name`` / ``quantifier``."""

    db_representation: Any | None = None
    """SQL-ready fragment or value (e.g. ``"date >= '...' AND date <= '...'"``)."""

    confidence: float = 0.0
    """0.0–1.0 confidence of the match."""

    matched_by: str = ""
    """Which strategy produced the match (e.g. ``"display"`` / ``"alias"`` / ``"llm"``)."""

    need_confirm: bool = False
    """True when the normalizer could not resolve the value; Phase 6 asks the user."""

    alternatives: list[Any] = field(default_factory=list)
    """Candidate values for the user to choose from (e.g. LIKE fallback results)."""
