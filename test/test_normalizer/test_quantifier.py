"""Tests for fuzzy quantifier detection (issue #28)."""

from normalizer.quantifier import detect_quantifier


class TestQuantifierDetector:
    def test_detects_大额(self):
        v = detect_quantifier("大额")
        assert v.need_confirm
        assert v.value_type == "quantifier"

    def test_detects_大量(self):
        assert detect_quantifier("大量").need_confirm

    def test_detects_小额(self):
        assert detect_quantifier("小额").need_confirm

    def test_detects_in_compound(self):
        assert detect_quantifier("大额订单").need_confirm

    def test_exact_number_not_quantifier(self):
        v = detect_quantifier("1000元")
        assert not v.need_confirm

    def test_numeric_not_quantifier(self):
        assert not detect_quantifier("500").need_confirm

    def test_unknown_word_not_quantifier(self):
        assert not detect_quantifier("普通").need_confirm

    def test_empty_string_not_quantifier(self):
        assert not detect_quantifier("").need_confirm

    def test_covers_all_presets(self):
        """All predefined quantifiers are detected."""
        for q in ["高价值", "大额", "小额", "适中", "大量", "少量"]:
            assert detect_quantifier(q).need_confirm, f"'{q}' should trigger need_confirm"
