"""V1 hot-word dictionary + industry thesaurus (Phase 5 / issue #30).

Maps common business terms directly to table.column or formula templates.
Locked formulas (``locked=True``) must NOT be rewritten by LLM.
V1 is a small curated set; bulk matching goes through vector search + LLM fallback.
No CRUD UI in V1 — edit this file to add/change entries.
"""

HOT_WORDS: dict[str, dict] = {
    # --- Aggregation / metrics ---
    "销售额": {
        "target_table": "orders",
        "formula": "SUM(price * quantity)",
        "description": "订单销售额",
        "locked": True,
    },
    "订单数": {
        "target_table": "orders",
        "formula": "COUNT(*)",
        "description": "订单总数",
        "locked": False,
    },
    "客单价": {
        "target_table": "orders",
        "formula": "SUM(amount) / COUNT(DISTINCT customer_id)",
        "description": "平均每客户的订单金额",
        "locked": True,
    },
    "库存量": {
        "target_table": "inventory",
        "target_column": "quantity",
        "description": "当前库存数量",
    },
    "毛利率": {
        "target_table": "orders",
        "formula": "(SUM(price) - SUM(cost)) / SUM(price)",
        "description": "毛利率",
        "locked": True,
    },
    "订单金额": {
        "target_table": "orders",
        "target_column": "amount",
        "description": "订单金额",
    },
    # --- Time-bound ---
    "本月新增": {
        "target_table": "orders",
        "target_column": "created_at",
        "description": "本月创建的订单",
    },
    # --- Status / filters ---
    "已完成": {
        "target_table": "orders",
        "target_column": "status",
        "description": "订单状态为已完成",
    },
    "已支付": {
        "target_table": "orders",
        "target_column": "status",
        "description": "订单状态为已支付",
    },
    "待发货": {
        "target_table": "orders",
        "target_column": "status",
        "description": "订单状态为待发货",
    },
    # --- Entities ---
    "客户": {
        "target_table": "customers",
        "target_column": "name",
        "description": "客户名称",
    },
    "产品": {
        "target_table": "products",
        "target_column": "name",
        "description": "产品名称",
    },
    "订单编号": {
        "target_table": "orders",
        "target_column": "id",
        "description": "订单编号",
    },
}

INDUSTRY_TERMS: dict[str, str] = {
    "GMV": "销售额",
    "SKU": "产品",
    "ARPU": "客单价",
    "日活": "日活跃用户",
    "周活": "周活跃用户",
    "复购率": "回头客比例",
    "客诉率": "客户投诉比例",
}
