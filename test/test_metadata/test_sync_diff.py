"""Tests for compute_diff — column_comment and table_comment change detection."""

import pytest

from metadata.sync import compute_diff


class TestColumnCommentDiff:
    """Verify compute_diff detects column_comment changes."""

    def test_column_comment_change_generates_modified(self):
        current = {
            "tables": [{"table_schema": "public", "table_name": "orders", "table_comment": None}],
            "columns": [
                {
                    "table_schema": "public",
                    "table_name": "orders",
                    "column_name": "status",
                    "data_type": "varchar",
                    "is_nullable": True,
                    "column_comment": "订单状态",
                },
            ],
            "indexes": [],
            "foreign_keys": [],
        }
        stored = {
            "tables": [{"table_schema": "public", "table_name": "orders", "table_comment": None}],
            "columns": [
                {
                    "table_schema": "public",
                    "table_name": "orders",
                    "column_name": "status",
                    "data_type": "varchar",
                    "is_nullable": True,
                    "column_comment": "状态",
                },
            ],
            "indexes": [],
            "foreign_keys": [],
        }

        changes = compute_diff(current, stored)
        modified = [c for c in changes if c["change_type"] == "column_modified"]
        assert len(modified) == 1
        assert modified[0]["object_name"] == "status"

    def test_column_comment_same_no_diff(self):
        base_col = {
            "table_schema": "public",
            "table_name": "orders",
            "column_name": "status",
            "data_type": "varchar",
            "is_nullable": True,
            "column_comment": "状态",
        }
        current = {
            "tables": [{"table_schema": "public", "table_name": "orders", "table_comment": None}],
            "columns": [base_col],
            "indexes": [],
            "foreign_keys": [],
        }
        stored = {
            "tables": [{"table_schema": "public", "table_name": "orders", "table_comment": None}],
            "columns": [dict(base_col)],
            "indexes": [],
            "foreign_keys": [],
        }

        changes = compute_diff(current, stored)
        modified = [c for c in changes if c["change_type"] == "column_modified"]
        assert len(modified) == 0

    def test_column_comment_from_null_to_value(self):
        current = {
            "tables": [{"table_schema": "public", "table_name": "t", "table_comment": None}],
            "columns": [
                {"table_schema": "public", "table_name": "t", "column_name": "c",
                 "data_type": "int", "is_nullable": True, "column_comment": "new comment"},
            ],
            "indexes": [],
            "foreign_keys": [],
        }
        stored = {
            "tables": [{"table_schema": "public", "table_name": "t", "table_comment": None}],
            "columns": [
                {"table_schema": "public", "table_name": "t", "column_name": "c",
                 "data_type": "int", "is_nullable": True, "column_comment": None},
            ],
            "indexes": [],
            "foreign_keys": [],
        }

        changes = compute_diff(current, stored)
        modified = [c for c in changes if c["change_type"] == "column_modified"]
        assert len(modified) == 1

    def test_column_comment_from_value_to_null(self):
        current = {
            "tables": [{"table_schema": "public", "table_name": "t", "table_comment": None}],
            "columns": [
                {"table_schema": "public", "table_name": "t", "column_name": "c",
                 "data_type": "int", "is_nullable": True, "column_comment": None},
            ],
            "indexes": [],
            "foreign_keys": [],
        }
        stored = {
            "tables": [{"table_schema": "public", "table_name": "t", "table_comment": None}],
            "columns": [
                {"table_schema": "public", "table_name": "t", "column_name": "c",
                 "data_type": "int", "is_nullable": True, "column_comment": "old"},
            ],
            "indexes": [],
            "foreign_keys": [],
        }

        changes = compute_diff(current, stored)
        modified = [c for c in changes if c["change_type"] == "column_modified"]
        assert len(modified) == 1


class TestTableCommentDiff:
    """Verify compute_diff detects table_comment changes."""

    def test_table_comment_change_generates_modified(self):
        current = {
            "tables": [{"table_schema": "public", "table_name": "orders", "table_comment": "订单主表"}],
            "columns": [],
            "indexes": [],
            "foreign_keys": [],
        }
        stored = {
            "tables": [{"table_schema": "public", "table_name": "orders", "table_comment": "订单"}],
            "columns": [],
            "indexes": [],
            "foreign_keys": [],
        }

        changes = compute_diff(current, stored)
        modified = [c for c in changes if c["change_type"] == "table_modified"]
        assert len(modified) == 1
        assert modified[0]["object_name"] == "orders"

    def test_table_comment_same_no_diff(self):
        current = {
            "tables": [{"table_schema": "public", "table_name": "orders", "table_comment": "订单"}],
            "columns": [],
            "indexes": [],
            "foreign_keys": [],
        }
        stored = {
            "tables": [{"table_schema": "public", "table_name": "orders", "table_comment": "订单"}],
            "columns": [],
            "indexes": [],
            "foreign_keys": [],
        }

        changes = compute_diff(current, stored)
        modified = [c for c in changes if c["change_type"] == "table_modified"]
        assert len(modified) == 0

    def test_table_comment_from_null_to_value(self):
        current = {
            "tables": [{"table_schema": "public", "table_name": "t", "table_comment": "new"}],
            "columns": [],
            "indexes": [],
            "foreign_keys": [],
        }
        stored = {
            "tables": [{"table_schema": "public", "table_name": "t", "table_comment": None}],
            "columns": [],
            "indexes": [],
            "foreign_keys": [],
        }

        changes = compute_diff(current, stored)
        modified = [c for c in changes if c["change_type"] == "table_modified"]
        assert len(modified) == 1
