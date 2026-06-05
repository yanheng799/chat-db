import pytest

MYSQL_SAMPLE_TABLES = [
    {"table_schema": "mydb", "table_name": "orders", "table_type": "BASE TABLE", "table_comment": "订单表"},
    {"table_schema": "mydb", "table_name": "customer_view", "table_type": "VIEW", "table_comment": None},
]

MYSQL_SAMPLE_COLUMNS = [
    {"table_schema": "mydb", "table_name": "orders", "column_name": "id", "data_type": "int", "is_nullable": "NO", "column_default": None, "column_comment": "主键", "is_primary_key": True, "ordinal_position": 1},
    {"table_schema": "mydb", "table_name": "orders", "column_name": "status", "data_type": "varchar", "is_nullable": "YES", "column_default": None, "column_comment": None, "is_primary_key": False, "ordinal_position": 2},
]

MYSQL_SAMPLE_INDEXES = [
    {"table_schema": "mydb", "table_name": "orders", "index_name": "idx_status", "column_names": ["status"], "is_unique": False},
]

MYSQL_SAMPLE_FKS = [
    {"table_schema": "mydb", "table_name": "orders", "constraint_name": "fk_customer", "column_name": "customer_id", "target_schema": "mydb", "target_table": "customers", "target_column": "id"},
]


def _mock_mysql_extractor():
    from metadata.extractor import MySqlMetadataExtractor

    class MockMySqlExtractor(MySqlMetadataExtractor):
        async def _fetch_tables(self, conn, schemas):
            return MYSQL_SAMPLE_TABLES

        async def _fetch_columns(self, conn, schemas):
            return MYSQL_SAMPLE_COLUMNS

        async def _fetch_indexes(self, conn, schemas):
            return MYSQL_SAMPLE_INDEXES

        async def _fetch_foreign_keys(self, conn, schemas):
            return MYSQL_SAMPLE_FKS

    return MockMySqlExtractor(None)


class TestMySqlMetadataExtractor:
    async def test_extract_returns_tables_with_table_type(self) -> None:
        extractor = _mock_mysql_extractor()
        result = await extractor.extract(schema_whitelist=None)
        tables = result["tables"]
        assert len(tables) == 2
        assert tables[0]["table_type"] == "BASE TABLE"
        assert tables[1]["table_type"] == "VIEW"

    async def test_extract_uses_table_schema_as_schema_name(self) -> None:
        extractor = _mock_mysql_extractor()
        result = await extractor.extract(schema_whitelist=None)
        assert result["tables"][0]["table_schema"] == "mydb"

    async def test_extract_maps_is_nullable_correctly(self) -> None:
        extractor = _mock_mysql_extractor()
        result = await extractor.extract(schema_whitelist=None)
        cols = [c for c in result["columns"] if c["table_name"] == "orders"]
        id_col = [c for c in cols if c["column_name"] == "id"][0]
        status_col = [c for c in cols if c["column_name"] == "status"][0]
        assert id_col["is_nullable"] == "NO"
        assert status_col["is_nullable"] == "YES"

    async def test_extract_maps_non_unique_to_is_unique(self) -> None:
        extractor = _mock_mysql_extractor()
        result = await extractor.extract(schema_whitelist=None)
        idx = result["indexes"][0]
        assert idx["is_unique"] is False

    async def test_extract_foreign_keys_from_key_column_usage(self) -> None:
        extractor = _mock_mysql_extractor()
        result = await extractor.extract(schema_whitelist=None)
        fk = result["foreign_keys"][0]
        assert fk["target_table"] == "customers"
        assert fk["column_name"] == "customer_id"

    async def test_mysql_system_databases_are_excluded(self) -> None:
        extractor = _mock_mysql_extractor()
        result = await extractor.extract(schema_whitelist=None)
        for t in result["tables"]:
            assert t["table_schema"] not in ("mysql", "information_schema", "performance_schema", "sys")

    async def test_schema_whitelist_filters(self) -> None:
        extractor = _mock_mysql_extractor()
        result = await extractor.extract(schema_whitelist=[{"schema": "other_db"}])
        assert len(result["tables"]) == 0

    async def test_implements_protocol_interface(self) -> None:
        from metadata.extractor import MetadataExtractor

        extractor = _mock_mysql_extractor()
        assert isinstance(extractor, MetadataExtractor)
