import pandas as pd
import pytest

from src.expenses.filters import (
    DEFAULT_FILTERS,
    TX_ALL,
    TX_GROSS,
    TX_NET,
    TX_REFUNDS,
    apply_filters,
    resolve_default_months,
)


@pytest.fixture
def full_df():
    """Minimal enriched frame carrying the columns apply_filters depends on."""
    rows = [
        # merchant, cost, ym, holder, category, is_payment, is_refund, is_installment
        (
            "EXAMPLE MARKET ONLINE",
            150.00,
            "2026-01",
            "CARDHOLDER_A",
            "shopping",
            False,
            False,
            False,
        ),
        ("SAMPLE GROCERY", 230.50, "2026-01", "CARDHOLDER_A", "groceries", False, False, False),
        ("DEMO STORE", 400.00, "2026-01", "CARDHOLDER_B", "shopping", False, False, True),
        ("DEMO TRANSIT RIDE", 50.00, "2026-02", "CARDHOLDER_A", "transport", False, False, False),
        ("SAMPLE STORE REFUND", -30.00, "2026-02", "CARDHOLDER_B", "shopping", False, True, False),
        ("PAGAMENTO FATURA", -1500.00, "2026-02", "CARDHOLDER_A", "not_found", True, False, False),
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "id",
            "cost",
            "year_month",
            "source_debt",
            "category",
            "is_payment",
            "is_refund",
            "is_installment",
        ],
    )


def test_empty_input_returns_empty():
    assert apply_filters(pd.DataFrame(), DEFAULT_FILTERS).empty


def test_default_filters_drop_only_payments(full_df):
    out = apply_filters(full_df, DEFAULT_FILTERS)
    assert len(out) == 5
    assert not out["is_payment"].any()


def test_tx_all_keeps_payments(full_df):
    out = apply_filters(full_df, {**DEFAULT_FILTERS, "tx_type": TX_ALL})
    assert len(out) == 6


def test_tx_gross_only_positive_non_payment(full_df):
    out = apply_filters(full_df, {**DEFAULT_FILTERS, "tx_type": TX_GROSS})
    assert len(out) == 4
    assert (out["cost"] > 0).all()


def test_tx_refunds_only(full_df):
    out = apply_filters(full_df, {**DEFAULT_FILTERS, "tx_type": TX_REFUNDS})
    assert out["id"].tolist() == ["SAMPLE STORE REFUND"]


def test_month_holder_category_and_search(full_df):
    out = apply_filters(
        full_df,
        {
            **DEFAULT_FILTERS,
            "tx_type": TX_NET,
            "selected_months": ["2026-01"],
            "selected_holders": ["CARDHOLDER_A"],
            "selected_categories": ["shopping", "groceries"],
        },
    )
    assert set(out["id"]) == {"EXAMPLE MARKET ONLINE", "SAMPLE GROCERY"}

    searched = apply_filters(full_df, {**DEFAULT_FILTERS, "search_id": "transit"})
    assert searched["id"].tolist() == ["DEMO TRANSIT RIDE"]


def test_installment_filters(full_df):
    only = apply_filters(full_df, {**DEFAULT_FILTERS, "installment_type": "Installments Only"})
    assert only["id"].tolist() == ["DEMO STORE"]
    single = apply_filters(full_df, {**DEFAULT_FILTERS, "installment_type": "Single Payment Only"})
    assert "DEMO STORE" not in single["id"].tolist()


def test_does_not_mutate_input(full_df):
    before = full_df.copy()
    apply_filters(full_df, {**DEFAULT_FILTERS, "selected_months": ["2026-01"]})
    pd.testing.assert_frame_equal(full_df, before)


def test_resolve_default_months():
    months = ["2026-03", "2026-02", "2026-01", "2025-12", "2025-11"]
    assert resolve_default_months("Last 3 months", months) == months[:3]
    assert resolve_default_months("All History", months) == months
    assert resolve_default_months("Custom", months) == months[:6]
