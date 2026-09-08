"""Pure (no-engine) tests for the database layer: the Silver load-shaping transform, the Bronze
composite dedup key, and the None-engine guards on the read/write helpers."""

import pandas as pd

from src.expenses.database import (
    _BRONZE_KEY_COLS,
    _bronze_row_key,
    _shape_silver_frame,
    align_table_columns,
    load_bronze_data,
    load_raw_data,
    load_silver_data,
    save_dataframe_replace,
)


def _silver_rows():
    """Raw Silver-layer shape (string dates, no derived columns) covering every branch of
    `_shape_silver_frame`: purchase, payment line, merchant refund, installment series, unknown
    category, an aliased merchant, and an exact duplicate of the first row."""
    base = {
        "date": "2026-01-05",
        "date_buy": "2025-12-01",
        "source_debt": " CARDHOLDER_A ",
        "installment": 0,
        "total_installments": 0,
        "source_file": "Invoice2026-01-05.csv",
    }
    return pd.DataFrame(
        [
            {**base, "id": "EXAMPLE STORE", "cost": 150.0, "category": "shopping"},
            {**base, "id": "PAGAMENTO FATURA", "cost": -1500.0, "category": "not_found"},
            {**base, "id": "SAMPLE GROCERY", "cost": -12.5, "category": "groceries"},
            {
                **base,
                "date_buy": "2025-12-05",
                "id": "EXAMPLE-MARKET SERVICE",
                "cost": 300.0,
                "installment": 2,
                "total_installments": 12,
                "category": "made_up_category",
            },
            {**base, "id": "EXAMPLE STORE", "cost": 150.0, "category": "shopping"},
        ]
    )


def test_shape_silver_frame_derived_columns():
    out = _shape_silver_frame(_silver_rows()).reset_index(drop=True)

    # exact-duplicate first row dropped
    assert len(out) == 4

    by_id = {row["id"]: row for _, row in out.iterrows()}

    assert bool(by_id["PAGAMENTO FATURA"]["is_payment"])
    assert not by_id["PAGAMENTO FATURA"]["is_refund"]  # negative payment is not a refund
    assert not by_id["EXAMPLE STORE"]["is_payment"]
    assert bool(by_id["SAMPLE GROCERY"]["is_refund"])  # negative, non-payment -> refund

    aliased = by_id["EXAMPLE MARKET"]  # id canonicalized by normalize_merchant_id
    assert bool(aliased["is_installment"])
    assert aliased["category"] == "not_found"  # unknown string coerced
    assert aliased["category_label"] == "Uncategorized"
    assert aliased["buy_year_month"] == "2025-12"
    assert aliased["day_of_week"] == "Friday"

    store = by_id["EXAMPLE STORE"]
    assert store["year"] == 2026
    assert store["month"] == 1
    assert store["year_month"] == "2026-01"
    assert store["day"] == 1
    assert not store["is_installment"]
    assert store["source_debt"] == "CARDHOLDER_A"  # trimmed

    assert out["installment"].dtype.kind == "i"
    assert out["cost"].dtype.kind == "f"


def test_shape_silver_frame_empty_passthrough():
    empty = pd.DataFrame()
    assert _shape_silver_frame(empty) is empty


def test_bronze_key_cols_and_row_key():
    assert _BRONZE_KEY_COLS == [
        "date",
        "date_buy",
        "id",
        "cost",
        "installment",
        "total_installments",
        "source_debt",
        "source_file",
    ]

    row_a = {
        "date": "2026-01-05",
        "date_buy": "2025-12-01",
        "id": "X",
        "cost": 10.0,
        "installment": 0,
        "total_installments": 0,
        "source_debt": "R",
        "source_file": "f",
    }
    row_b = {**row_a, "created_at": "2026-01-05 10:00:00"}  # extra col not in the key
    assert _bronze_row_key(row_a) == "2026-01-05_2025-12-01_X_10.0_0_0_R_f"
    assert _bronze_row_key(row_a) == _bronze_row_key(row_b)


def test_save_dataframe_replace_none_engine_noop():
    save_dataframe_replace(pd.DataFrame(), engine=None)
    save_dataframe_replace(pd.DataFrame([{"id": "X"}]), engine=None)


def test_align_table_columns_none_engine_noop():
    align_table_columns(None, {"foo": "VARCHAR(10)"})


def test_layer_loaders_return_empty_without_engine(monkeypatch):
    monkeypatch.setattr("src.expenses.database.get_db_engine", lambda *a, **k: None)
    monkeypatch.setattr("src.expenses.database.create_medallion_tables", lambda *a, **k: None)
    for loader in (load_raw_data, load_bronze_data, load_silver_data):
        out = loader()
        assert isinstance(out, pd.DataFrame)
        assert out.empty
