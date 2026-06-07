"""L1 field name splitting — translate column names to Chinese descriptions.

Supports two naming conventions:
- **snake_case**: ``order_status`` → ["order", "status"] → "订单状态"
- **CamelCase**:  ``orderStatus``  → ["order", "Status"] → "订单状态"

Each word must be found in the built-in :pymod:`learning.word_table`.  If any
word is missing the whole field is skipped and left for L2 (LLM) processing.
"""

from __future__ import annotations

import re

from learning.word_table import WORD_TABLE


def split_field_name(name: str) -> str | None:
    """Split a field name into words and translate to Chinese.

    Returns the Chinese translation, or ``None`` if any word is not
    in the word table.
    """
    if not name:
        return None

    words = _split_into_words(name)
    if not words:
        return None

    translations: list[str] = []
    for word in words:
        key = word.lower()
        if key not in WORD_TABLE:
            return None
        translations.append(WORD_TABLE[key])

    return "".join(translations)


def _split_into_words(name: str) -> list[str]:
    """Split a field name into individual words (snake_case or CamelCase)."""
    if "_" in name:
        # snake_case — also handles leading/trailing/double underscores
        parts = name.split("_")
        return [p for p in parts if p]

    # CamelCase: insert separator at case transitions
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    parts = s.split("_")
    return [p for p in parts if p]
