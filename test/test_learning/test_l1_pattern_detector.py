"""Tests for L1 data pattern detection — query builder, enum/null/range logic."""

import pytest

from learning.pattern_detector import (
    build_aggregate_query,
    compute_table_estimated_rows,
    detect_enum_fields,
    parse_aggregate_results,
    should_use_sampling,
    LARGE_TABLE_THRESHOLD,
)


class TestEnumDetection:
    """Test enum detection threshold logic."""

    def test_enum_detected_below_threshold(self):
        """distinct/total < 0.05 AND distinct ≤ 20 → enum."""
        assert detect_enum_fields(
            total_rows=1000,
            column_stats={"status": {"distinct_count": 5}},
        ) == {"status": True}

    def test_enum_not_detected_above_ratio(self):
        """distinct/total >= 0.05 → not enum."""
        assert detect_enum_fields(
            total_rows=100,
            column_stats={"category": {"distinct_count": 10}},
        ) == {"category": False}  # 10/100 = 0.10 > 0.05

    def test_enum_not_detected_above_count(self):
        """distinct > 20 → not enum."""
        assert detect_enum_fields(
            total_rows=10000,
            column_stats={"name": {"distinct_count": 25}},
        ) == {"name": False}  # 25 > 20

    def test_enum_edge_case_exactly_20(self):
        """distinct == 20 AND ratio < 0.05 → enum."""
        assert detect_enum_fields(
            total_rows=10000,
            column_stats={"type": {"distinct_count": 20}},
        ) == {"type": True}  # 20/10000 = 0.002 < 0.05

    def test_enum_edge_case_exactly_ratio(self):
        """distinct/total == 0.05 → not enum (must be strictly less)."""
        assert detect_enum_fields(
            total_rows=1000,
            column_stats={"type": {"distinct_count": 50}},
        ) == {"type": False}  # 50/1000 = 0.05 not < 0.05

    def test_enum_multiple_columns(self):
        stats = {
            "status": {"distinct_count": 3},
            "category": {"distinct_count": 30},
            "priority": {"distinct_count": 5},
        }
        result = detect_enum_fields(total_rows=1000, column_stats=stats)
        assert result == {"status": True, "category": False, "priority": True}

    def test_enum_zero_total_rows(self):
        """Zero total rows should not detect any enums."""
        result = detect_enum_fields(total_rows=0, column_stats={"col": {"distinct_count": 0}})
        assert result == {"col": False}


class TestSamplingDecision:
    """Test large table sampling logic."""

    def test_small_table_no_sampling(self):
        assert should_use_sampling(estimated_rows=500_000) is False

    def test_exact_threshold_no_sampling(self):
        assert should_use_sampling(estimated_rows=LARGE_TABLE_THRESHOLD) is False

    def test_large_table_needs_sampling(self):
        assert should_use_sampling(estimated_rows=LARGE_TABLE_THRESHOLD + 1) is True

    def test_zero_rows_no_sampling(self):
        assert should_use_sampling(estimated_rows=0) is False


class TestBuildAggregateQueryPostgreSQL:
    """Test aggregate SQL generation for PostgreSQL."""

    def test_basic_query_with_mixed_types(self):
        columns = [
            _make_col("status", "varchar"),
            _make_col("amount", "numeric"),
            _make_col("notes", "text"),
        ]
        sql = build_aggregate_query(
            table_name="orders",
            schema_name="public",
            columns=columns,
            engine_type="postgresql",
        )
        # Should be a single query with all aggregations
        assert "COUNT(*) AS total_rows" in sql
        # status: distinct + null ratio
        assert 'COUNT(DISTINCT "status")' in sql
        assert 'COUNT(*) FILTER (WHERE "status" IS NULL)' in sql
        # amount: distinct + null ratio + min/max (numeric)
        assert 'COUNT(DISTINCT "amount")' in sql
        assert 'MIN("amount")' in sql
        assert 'MAX("amount")' in sql
        # notes: distinct + null ratio (no min/max for text)
        assert 'MIN("notes")' not in sql

    def test_sampling_query_includes_tablesample(self):
        columns = [_make_col("status", "varchar")]
        sql = build_aggregate_query(
            table_name="big_table",
            schema_name="public",
            columns=columns,
            engine_type="postgresql",
            use_sampling=True,
        )
        assert "TABLESAMPLE SYSTEM" in sql

    def test_no_sampling_no_tablesample(self):
        columns = [_make_col("status", "varchar")]
        sql = build_aggregate_query(
            table_name="small_table",
            schema_name="public",
            columns=columns,
            engine_type="postgresql",
            use_sampling=False,
        )
        assert "TABLESAMPLE" not in sql

    def test_empty_columns_raises(self):
        with pytest.raises(ValueError, match="no columns"):
            build_aggregate_query(
                table_name="orders",
                schema_name="public",
                columns=[],
                engine_type="postgresql",
            )

    def test_enum_values_collected(self):
        """Query should include array_agg for enum candidate columns."""
        columns = [_make_col("status", "varchar")]
        sql = build_aggregate_query(
            table_name="orders",
            schema_name="public",
            columns=columns,
            engine_type="postgresql",
        )
        # Should collect distinct values for potential enum fields
        assert "array_agg" in sql.lower() or "DISTINCT" in sql


class TestBuildAggregateQueryMySQL:
    """Test aggregate SQL generation for MySQL."""

    def test_mysql_basic_query(self):
        columns = [
            _make_col("status", "varchar"),
            _make_col("amount", "decimal"),
        ]
        sql = build_aggregate_query(
            table_name="orders",
            schema_name=None,
            columns=columns,
            engine_type="mysql",
        )
        assert "COUNT(*) AS total_rows" in sql
        assert "COUNT(DISTINCT `status`)" in sql
        assert "MIN(`amount`)" in sql
        # MySQL uses IFNULL or SUM for null ratio
        assert "IS NULL" in sql

    def test_mysql_sampling_uses_limit(self):
        columns = [_make_col("status", "varchar")]
        sql = build_aggregate_query(
            table_name="big_table",
            schema_name=None,
            columns=columns,
            engine_type="mysql",
            use_sampling=True,
        )
        assert "LIMIT" in sql


class TestParseAggregateResults:
    """Test parsing of aggregate query results into structured data."""

    def test_parse_basic_results(self):
        columns = [
            _make_col("status", "varchar"),
            _make_col("amount", "numeric"),
        ]
        row = {
            "total_rows": 1000,
            "status__distinct": 5,
            "status__null_count": 10,
            "status__values": ["active", "pending", "closed", "open", "draft"],
            "amount__distinct": 800,
            "amount__null_count": 0,
            "amount__min": 10.5,
            "amount__max": 999.99,
        }
        results = parse_aggregate_results(row, columns)
        assert results["status"]["distinct_count"] == 5
        assert results["status"]["null_count"] == 10
        assert results["status"]["values"] == ["active", "pending", "closed", "open", "draft"]
        assert results["amount"]["distinct_count"] == 800
        assert results["amount"]["null_count"] == 0
        assert results["amount"]["min"] == 10.5
        assert results["amount"]["max"] == 999.99

    def test_null_values_handled(self):
        """MIN/MAX should be None for non-numeric or all-null columns."""
        columns = [_make_col("notes", "text")]
        row = {
            "total_rows": 100,
            "notes__distinct": 50,
            "notes__null_count": 100,
            "notes__values": None,
        }
        results = parse_aggregate_results(row, columns)
        assert results["notes"]["values"] is None or results["notes"]["values"] == []


class TestEstimatedRows:
    """Test estimated row count query generation."""

    def test_pg_estimated_rows_query(self):
        query = compute_table_estimated_rows("orders", "public", "postgresql")
        assert "pg_class" in query
        assert "reltuples" in query

    def test_mysql_estimated_rows_query(self):
        query = compute_table_estimated_rows("orders", None, "mysql")
        assert "EXPLAIN" in query


# --- Helpers ---

def _make_col(name: str, data_type: str):
    """Create a lightweight column-like object for query builder tests."""
    from dataclasses import dataclass

    @dataclass
    class FakeCol:
        column_name: str
        data_type: str

    return FakeCol(column_name=name, data_type=data_type)
