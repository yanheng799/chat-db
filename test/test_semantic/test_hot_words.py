"""Tests for V1 hot-words dictionary (issue #30)."""

from semantic.hot_words import HOT_WORDS, INDUSTRY_TERMS


class TestHotWords:
    def test_sales_amount_found(self):
        assert "销售额" in HOT_WORDS
        assert HOT_WORDS["销售额"]["locked"] is True

    def test_formulas_have_target_table(self):
        for term, entry in HOT_WORDS.items():
            assert "target_table" in entry, f"{term}: missing target_table"

    def test_locked_entries_marked(self):
        locked = {k for k, v in HOT_WORDS.items() if v.get("locked")}
        assert "销售额" in locked or "毛利率" in locked, "at least one formula locked"

    def test_industry_terms_are_translations(self):
        assert "GMV" in INDUSTRY_TERMS
        assert isinstance(INDUSTRY_TERMS["GMV"], str)

    def test_industry_terms_are_valid(self):
        for v in INDUSTRY_TERMS.values():
            assert isinstance(v, str) and len(v) > 0
