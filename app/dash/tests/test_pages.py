"""Bodies of every secondary Dash tab (expenses_dash.pages), with and without data."""

import pandas as pd
import pytest

from expenses_dash.analyses import (
    category_view,
    habits_view,
    reports_view,
    trends_view,
    watchlist_view,
)
from expenses_dash.pages import (
    NO_ROWS,
    _label_to_key,
    category_page,
    habits_page,
    html_scroll,
    reports_page,
    trends_page,
    watchlist_page,
)

PAGES = [
    (trends_page, trends_view, 3),
    (habits_page, habits_view, 4),
    (watchlist_page, watchlist_view, 0),
    (reports_page, reports_view, 1),
]


@pytest.mark.parametrize(("page", "view", "n_graphs"), PAGES)
def test_pages_with_data(silver_history_df, graphs, page, view, n_graphs):
    body = page(view(silver_history_df, "Last 6 months"))
    assert body
    assert len(graphs(body)) == n_graphs


@pytest.mark.parametrize(("page", "view", "_n"), PAGES[:3])
def test_pages_without_data(texts, page, view, _n):
    assert NO_ROWS in texts(page(view(pd.DataFrame())))


def test_reports_page_without_installments(texts):
    assert "No open installment purchases." in texts(reports_page(reports_view(pd.DataFrame())))


def test_category_page(silver_history_df, graphs, texts):
    body = category_page(category_view(silver_history_df, "All History", selected="food"))
    assert len(graphs(body)) == 2
    assert "Food & Dining" in texts(body)
    assert NO_ROWS in texts(category_page(category_view(pd.DataFrame())))


def test_kpi_tones_follow_meaning(silver_history_df):
    reports = reports_page(reports_view(silver_history_df, "Last 6 months"))
    first_card = reports[0].children[0]
    note = first_card.children[2]
    assert "pe-tone-bad" in note.className  # synthetic data is far above the 10k limit


def test_label_to_key_and_scroll():
    assert _label_to_key("Food & Dining") == "food"
    assert _label_to_key("desconhecida") == "not_found"
    assert html_scroll("x").className == "pe-scroll"
