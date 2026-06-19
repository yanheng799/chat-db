"""Tests for LangGraph state + routing (#37)."""

from agents.graph import classify_query, build_graph


class TestClassifyQuery:
    def test_comparison_routes_multi(self):
        assert classify_query({"nl_text": "对比本月和上月的销售额"})["route"] == "multi"

    def test_sequential_routes_multi(self):
        assert classify_query({"nl_text": "先查订单再查客户"})["route"] == "multi"

    def test_simple_routes_single(self):
        assert classify_query({"nl_text": "查一下昨天的订单总数"})["route"] == "single"

    def test_multi_table_routes_multi(self):
        s = {"nl_text": "包含客户名的订单", "matched_fields": [
            {"table": "orders"}, {"table": "customers"}]}
        assert classify_query(s)["route"] == "multi"

    def test_single_table_routes_single(self):
        s = {"nl_text": "订单列表", "matched_fields": [{"table": "orders"}]}
        assert classify_query(s)["route"] == "single"


class TestGraphBuild:
    def test_graph_compiles(self):
        graph = build_graph()
        assert graph is not None
