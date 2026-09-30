"""Pure helpers inside the Streamlit tab modules."""

import pytest

from expenses_streamlit.tabs.category import _category_options, _day_of_week_table
from expenses_streamlit.tabs.reports import _installments_label, _invoice_totals
from expenses_streamlit.tabs.watchlist import _uncategorized


def test_installments_label():
    assert _installments_label(2, 6) == "2/6"
    assert _installments_label(0, 0) == "Single payment"
    assert _installments_label(1, 1) == "Single payment"


def test_invoice_totals(silver_history_df):
    expenses = silver_history_df[~silver_history_df["is_payment"]]
    table = _invoice_totals(expenses)
    assert table["Invoice"].nunique() == expenses["year_month"].nunique()
    assert table["Invoice date"].is_monotonic_decreasing
    assert table["Net total"].sum() == pytest.approx(expenses["cost"].sum())
    assert (table["Gross"] + table["Refunds"]).tolist() == pytest.approx(
        table["Net total"].tolist()
    )


def test_uncategorized(silver_history_df):
    expenses = silver_history_df[~silver_history_df["is_payment"]]
    table, total, share = _uncategorized(expenses)
    positive = expenses[expenses["cost"] > 0]
    expected = positive[positive["category"] == "not_found"]["cost"].sum()
    assert total == pytest.approx(expected)
    assert share == pytest.approx(expected / positive["cost"].sum() * 100)
    assert table["Total"].is_monotonic_decreasing
    empty_table, empty_total, empty_share = _uncategorized(expenses.iloc[0:0])
    assert empty_table.empty and empty_total == 0 and empty_share == 0


def test_category_options_puts_uncategorized_last(silver_history_df):
    options = _category_options(silver_history_df)
    assert options[-1] == "not_found"
    assert sorted(options[:-1]) == options[:-1]


def test_day_of_week_table(silver_history_df):
    food = silver_history_df[
        (silver_history_df["category"] == "food") & (silver_history_df["cost"] > 0)
    ]
    table = _day_of_week_table(food, float(food["cost"].sum()))
    assert table["Day"].str.startswith("Monday").iloc[0]
    assert len(table) == 7
    assert table["Transactions"].sum() == len(food)
    assert table["Share"].sum() == pytest.approx(1.0)
    assert _day_of_week_table(food.iloc[0:0], 0.0)["Total"].sum() == 0
