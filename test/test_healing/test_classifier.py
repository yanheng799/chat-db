"""Tests for error classifier (#41)."""

from healing.classifier import ErrorType, classify_error


class TestClassifyError:
    def test_pg_table_not_found_by_code(self):
        assert classify_error("relation does not exist", "postgresql", pgcode="42P01") == ErrorType.TABLE_NOT_FOUND

    def test_pg_column_not_found_by_code(self):
        assert classify_error("column does not exist", "postgresql", pgcode="42703") == ErrorType.COLUMN_NOT_FOUND

    def test_mysql_table_not_found_by_errno(self):
        assert classify_error("Table doesn't exist", "mysql", errno=1146) == ErrorType.TABLE_NOT_FOUND

    def test_fallback_regex_table(self):
        assert classify_error("relation \"orders\" does not exist", "postgresql") == ErrorType.TABLE_NOT_FOUND

    def test_fallback_regex_syntax(self):
        assert classify_error("syntax error at or near", "postgresql") == ErrorType.SQL_SYNTAX_ERROR

    def test_no_match_returns_other(self):
        assert classify_error("unknown unexpected error xyz", "postgresql") == ErrorType.OTHER
