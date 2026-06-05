from metadata.sync import compute_diff


class TestDiffEngine:
    def test_detect_table_added(self) -> None:
        current = {"tables": [{"table_schema": "public", "table_name": "orders"}], "columns": [], "indexes": [], "foreign_keys": []}
        stored = {"tables": [], "columns": [], "indexes": [], "foreign_keys": []}
        changes = compute_diff(current, stored)
        assert any(c["change_type"] == "table_added" and c["table_name"] == "orders" for c in changes)

    def test_detect_table_removed(self) -> None:
        current = {"tables": [], "columns": [], "indexes": [], "foreign_keys": []}
        stored = {"tables": [{"table_schema": "public", "table_name": "orders"}], "columns": [], "indexes": [], "foreign_keys": []}
        changes = compute_diff(current, stored)
        assert any(c["change_type"] == "table_removed" and c["table_name"] == "orders" for c in changes)

    def test_detect_column_added(self) -> None:
        current = {
            "tables": [{"table_schema": "public", "table_name": "orders"}],
            "columns": [
                {"table_schema": "public", "table_name": "orders", "column_name": "id", "data_type": "int"},
                {"table_schema": "public", "table_name": "orders", "column_name": "status", "data_type": "varchar"},
            ],
            "indexes": [], "foreign_keys": [],
        }
        stored = {
            "tables": [{"table_schema": "public", "table_name": "orders"}],
            "columns": [{"table_schema": "public", "table_name": "orders", "column_name": "id", "data_type": "int"}],
            "indexes": [], "foreign_keys": [],
        }
        changes = compute_diff(current, stored)
        assert any(c["change_type"] == "column_added" and c["object_name"] == "status" for c in changes)

    def test_detect_column_removed(self) -> None:
        current = {
            "tables": [{"table_schema": "public", "table_name": "orders"}],
            "columns": [{"table_schema": "public", "table_name": "orders", "column_name": "id", "data_type": "int"}],
            "indexes": [], "foreign_keys": [],
        }
        stored = {
            "tables": [{"table_schema": "public", "table_name": "orders"}],
            "columns": [
                {"table_schema": "public", "table_name": "orders", "column_name": "id", "data_type": "int"},
                {"table_schema": "public", "table_name": "orders", "column_name": "status", "data_type": "varchar"},
            ],
            "indexes": [], "foreign_keys": [],
        }
        changes = compute_diff(current, stored)
        assert any(c["change_type"] == "column_removed" and c["object_name"] == "status" for c in changes)

    def test_detect_column_modified(self) -> None:
        current = {
            "tables": [{"table_schema": "public", "table_name": "orders"}],
            "columns": [{"table_schema": "public", "table_name": "orders", "column_name": "status", "data_type": "text"}],
            "indexes": [], "foreign_keys": [],
        }
        stored = {
            "tables": [{"table_schema": "public", "table_name": "orders"}],
            "columns": [{"table_schema": "public", "table_name": "orders", "column_name": "status", "data_type": "varchar"}],
            "indexes": [], "foreign_keys": [],
        }
        changes = compute_diff(current, stored)
        assert any(c["change_type"] == "column_modified" and c["object_name"] == "status" for c in changes)

    def test_detect_index_added(self) -> None:
        current = {"tables": [{"table_schema": "public", "table_name": "orders"}], "columns": [], "indexes": [{"table_schema": "public", "table_name": "orders", "index_name": "idx_new"}], "foreign_keys": []}
        stored = {"tables": [{"table_schema": "public", "table_name": "orders"}], "columns": [], "indexes": [], "foreign_keys": []}
        changes = compute_diff(current, stored)
        assert any(c["change_type"] == "index_added" and c["object_name"] == "idx_new" for c in changes)

    def test_detect_index_removed(self) -> None:
        current = {"tables": [{"table_schema": "public", "table_name": "orders"}], "columns": [], "indexes": [], "foreign_keys": []}
        stored = {"tables": [{"table_schema": "public", "table_name": "orders"}], "columns": [], "indexes": [{"table_schema": "public", "table_name": "orders", "index_name": "idx_old"}], "foreign_keys": []}
        changes = compute_diff(current, stored)
        assert any(c["change_type"] == "index_removed" and c["object_name"] == "idx_old" for c in changes)

    def test_detect_fk_added(self) -> None:
        current = {"tables": [{"table_schema": "public", "table_name": "orders"}], "columns": [], "indexes": [], "foreign_keys": [{"table_schema": "public", "table_name": "orders", "constraint_name": "fk_new"}]}
        stored = {"tables": [{"table_schema": "public", "table_name": "orders"}], "columns": [], "indexes": [], "foreign_keys": []}
        changes = compute_diff(current, stored)
        assert any(c["change_type"] == "fk_added" and c["object_name"] == "fk_new" for c in changes)

    def test_detect_fk_removed(self) -> None:
        current = {"tables": [{"table_schema": "public", "table_name": "orders"}], "columns": [], "indexes": [], "foreign_keys": []}
        stored = {"tables": [{"table_schema": "public", "table_name": "orders"}], "columns": [], "indexes": [], "foreign_keys": [{"table_schema": "public", "table_name": "orders", "constraint_name": "fk_old"}]}
        changes = compute_diff(current, stored)
        assert any(c["change_type"] == "fk_removed" and c["object_name"] == "fk_old" for c in changes)

    def test_no_changes_when_identical(self) -> None:
        data = {"tables": [{"table_schema": "public", "table_name": "orders"}], "columns": [{"table_schema": "public", "table_name": "orders", "column_name": "id", "data_type": "int"}], "indexes": [], "foreign_keys": []}
        changes = compute_diff(data, data)
        assert len(changes) == 0
