"""Tests for SQL security validator (#33)."""

from sql.security import validate_sql


class TestSecurityValidator:
    def test_allows_valid_select(self):
        assert validate_sql("SELECT id, name FROM orders LIMIT 100")["passed"]

    def test_blocks_drop(self):
        r = validate_sql("DROP TABLE orders")
        assert not r["passed"]
        assert "DROP" in r["reason"]

    def test_blocks_delete(self):
        assert not validate_sql("DELETE FROM orders WHERE id=1")["passed"]

    def test_blocks_insert(self):
        assert not validate_sql("INSERT INTO orders VALUES (1)")["passed"]

    def test_requires_limit(self):
        assert not validate_sql("SELECT id FROM orders")["passed"]

    def test_blocks_limit_too_large(self):
        assert not validate_sql("SELECT id FROM orders LIMIT 2000")["passed"]

    def test_blocks_select_star(self):
        assert not validate_sql("SELECT * FROM orders LIMIT 10")["passed"]

    def test_blocks_multi_table_join(self):
        assert not validate_sql("SELECT a.id FROM orders a JOIN customers b ON a.cid=b.id LIMIT 10")["passed"]
