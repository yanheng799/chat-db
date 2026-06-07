from __future__ import annotations


def compute_diff(current: dict, stored: dict) -> list[dict]:
    """Compare current schema with stored metadata, return list of changes.

    Each change is a dict with keys: change_type, schema_name, table_name,
    object_name, before_value, after_value.
    """
    changes: list[dict] = []

    # ── Table-level diff ─────────────────────────────────────────
    current_tables = {(t["table_schema"], t["table_name"]): t for t in current["tables"]}
    stored_tables = {(t["table_schema"], t["table_name"]): t for t in stored["tables"]}

    for key, ct in current_tables.items():
        if key not in stored_tables:
            changes.append(
                {
                    "change_type": "table_added",
                    "schema_name": ct["table_schema"],
                    "table_name": ct["table_name"],
                    "object_name": ct["table_name"],
                    "before_value": None,
                    "after_value": ct,
                }
            )
    for key, st in stored_tables.items():
        if key not in current_tables:
            changes.append(
                {
                    "change_type": "table_removed",
                    "schema_name": st["table_schema"],
                    "table_name": st["table_name"],
                    "object_name": st["table_name"],
                    "before_value": st,
                    "after_value": None,
                }
            )
        else:
            # Check for table-level modifications (e.g. table_comment change)
            ct = current_tables[key]
            if ct.get("table_comment") != st.get("table_comment"):
                changes.append(
                    {
                        "change_type": "table_modified",
                        "schema_name": ct["table_schema"],
                        "table_name": ct["table_name"],
                        "object_name": ct["table_name"],
                        "before_value": st,
                        "after_value": ct,
                    }
                )

    # ── Column-level diff ────────────────────────────────────────
    current_cols = {(c["table_schema"], c["table_name"], c["column_name"]): c for c in current["columns"]}
    stored_cols = {(c["table_schema"], c["table_name"], c["column_name"]): c for c in stored["columns"]}

    for key, cc in current_cols.items():
        if key not in stored_cols:
            # Only report column_added if the table wasn't already added
            if (key[0], key[1]) in stored_tables:
                changes.append(
                    {
                        "change_type": "column_added",
                        "schema_name": cc["table_schema"],
                        "table_name": cc["table_name"],
                        "object_name": cc["column_name"],
                        "before_value": None,
                        "after_value": cc,
                    }
                )
        else:
            # Check for modifications
            sc = stored_cols[key]
            if (
                cc.get("data_type") != sc.get("data_type")
                or cc.get("is_nullable") != sc.get("is_nullable")
                or cc.get("column_comment") != sc.get("column_comment")
            ):
                changes.append(
                    {
                        "change_type": "column_modified",
                        "schema_name": cc["table_schema"],
                        "table_name": cc["table_name"],
                        "object_name": cc["column_name"],
                        "before_value": sc,
                        "after_value": cc,
                    }
                )
    for key, sc in stored_cols.items():
        # Only report column_removed if the table wasn't already removed
        if key not in current_cols and (key[0], key[1]) in current_tables:
            changes.append(
                {
                    "change_type": "column_removed",
                    "schema_name": sc["table_schema"],
                    "table_name": sc["table_name"],
                    "object_name": sc["column_name"],
                    "before_value": sc,
                    "after_value": None,
                }
            )

    # ── Index-level diff ─────────────────────────────────────────
    current_idx = {(i["table_schema"], i["table_name"], i["index_name"]): i for i in current["indexes"]}
    stored_idx = {(i["table_schema"], i["table_name"], i["index_name"]): i for i in stored["indexes"]}

    for key, ci in current_idx.items():
        if key not in stored_idx and (key[0], key[1]) in stored_tables:
            changes.append(
                {
                    "change_type": "index_added",
                    "schema_name": ci["table_schema"],
                    "table_name": ci["table_name"],
                    "object_name": ci["index_name"],
                    "before_value": None,
                    "after_value": ci,
                }
            )
    for key, si in stored_idx.items():
        if key not in current_idx and (key[0], key[1]) in current_tables:
            changes.append(
                {
                    "change_type": "index_removed",
                    "schema_name": si["table_schema"],
                    "table_name": si["table_name"],
                    "object_name": si["index_name"],
                    "before_value": si,
                    "after_value": None,
                }
            )

    # ── FK-level diff ────────────────────────────────────────────
    current_fks = {(f["table_schema"], f["table_name"], f["constraint_name"]): f for f in current["foreign_keys"]}
    stored_fks = {(f["table_schema"], f["table_name"], f["constraint_name"]): f for f in stored["foreign_keys"]}

    for key, cf in current_fks.items():
        if key not in stored_fks and (key[0], key[1]) in stored_tables:
            changes.append(
                {
                    "change_type": "fk_added",
                    "schema_name": cf["table_schema"],
                    "table_name": cf["table_name"],
                    "object_name": cf["constraint_name"],
                    "before_value": None,
                    "after_value": cf,
                }
            )
    for key, sf in stored_fks.items():
        if key not in current_fks and (key[0], key[1]) in current_tables:
            changes.append(
                {
                    "change_type": "fk_removed",
                    "schema_name": sf["table_schema"],
                    "table_name": sf["table_name"],
                    "object_name": sf["constraint_name"],
                    "before_value": sf,
                    "after_value": None,
                }
            )

    return changes
