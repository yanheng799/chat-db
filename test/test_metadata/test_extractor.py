import pytest


SAMPLE_TABLES = [
    {
        "table_schema": "public",
        "table_name": "orders",
        "table_type": "BASE TABLE",
        "table_comment": "订单表",
    },
    {
        "table_schema": "public",
        "table_name": "customer_view",
        "table_type": "VIEW",
        "table_comment": None,
    },
]

SAMPLE_COLUMNS = [
    {
        "table_schema": "public",
        "table_name": "orders",
        "column_name": "id",
        "data_type": "integer",
        "is_nullable": "NO",
        "column_default": "nextval('orders_id_seq')",
        "column_comment": "主键",
        "is_primary_key": True,
        "ordinal_position": 1,
    },
    {
        "table_schema": "public",
        "table_name": "orders",
        "column_name": "status",
        "data_type": "varchar",
        "is_nullable": "YES",
        "column_default": None,
        "column_comment": None,
        "is_primary_key": False,
        "ordinal_position": 2,
    },
]

SAMPLE_INDEXES = [
    {
        "table_schema": "public",
        "table_name": "orders",
        "index_name": "idx_orders_status",
        "column_names": ["status"],
        "is_unique": False,
    },
]

SAMPLE_FOREIGN_KEYS = [
    {
        "table_schema": "public",
        "table_name": "orders",
        "constraint_name": "fk_orders_customer",
        "column_name": "customer_id",
        "target_schema": "public",
        "target_table": "customers",
        "target_column": "id",
    },
]


def _mock_pg_extractor():
    from metadata.extractor import PgMetadataExtractor

    class MockPgExtractor(PgMetadataExtractor):
        async def _fetch_tables(self, conn, schemas):
            return SAMPLE_TABLES

        async def _fetch_columns(self, conn, schemas):
            return SAMPLE_COLUMNS

        async def _fetch_indexes(self, conn, schemas):
            return SAMPLE_INDEXES

        async def _fetch_foreign_keys(self, conn, schemas):
            return SAMPLE_FOREIGN_KEYS

    return MockPgExtractor(None)


class TestPgMetadataExtractor:
    async def test_extract_returns_tables(self) -> None:
        extractor = _mock_pg_extractor()
        result = await extractor.extract(schema_whitelist=None)
        assert len(result["tables"]) == 2
        assert result["tables"][0]["table_name"] == "orders"
        assert result["tables"][0]["table_type"] == "BASE TABLE"

    async def test_extract_returns_columns_with_pk_info(self) -> None:
        extractor = _mock_pg_extractor()
        result = await extractor.extract(schema_whitelist=None)
        cols = [c for c in result["columns"] if c["table_name"] == "orders"]
        assert len(cols) == 2
        pk_col = [c for c in cols if c["is_primary_key"]][0]
        assert pk_col["column_name"] == "id"

    async def test_extract_returns_indexes(self) -> None:
        extractor = _mock_pg_extractor()
        result = await extractor.extract(schema_whitelist=None)
        assert len(result["indexes"]) == 1
        assert result["indexes"][0]["index_name"] == "idx_orders_status"

    async def test_extract_returns_foreign_keys(self) -> None:
        extractor = _mock_pg_extractor()
        result = await extractor.extract(schema_whitelist=None)
        assert len(result["foreign_keys"]) == 1
        assert result["foreign_keys"][0]["target_table"] == "customers"

    async def test_schema_whitelist_filters_tables(self) -> None:
        extractor = _mock_pg_extractor()
        result = await extractor.extract(schema_whitelist=[{"schema": "sales"}])
        # Mock returns all tables; whitelist filters to none since only "public" exists
        # and "sales" != "public"
        assert len(result["tables"]) == 0

    async def test_system_schemas_are_excluded(self) -> None:
        extractor = _mock_pg_extractor()
        result = await extractor.extract(schema_whitelist=None)
        # Verify pg_catalog is excluded
        for t in result["tables"]:
            assert t["table_schema"] not in (
                "pg_catalog",
                "information_schema",
                "pg_toast",
            )
