"""Secondary Dash tabs: view models (analyses.py) and rendered bodies (callbacks/pages)."""

import pandas as pd
import plotly.graph_objects as go
import pytest
from dash import dcc

from app.dash.analyses import (
    TICKET_LABELS,
    category_month_matrix,
    category_options,
    category_view,
    export_frame,
    habits_view,
    new_merchants,
    reports_view,
    trends_view,
    watchlist_view,
)
from app.dash.callbacks import render_category, render_tab
from app.dash.data import slice_data
from app.dash.figures import (
    category_history_figure,
    comparison_figure,
    limit_figure,
    yoy_figure,
)
from app.dash.theme import PALETTE
from src.expenses.analytics import get_recurring_merchants


def _walk(component):
    stack = [component]
    while stack:
        node = stack.pop()
        if isinstance(node, list | tuple):
            stack.extend(node)
            continue
        yield node
        children = getattr(node, "children", None)
        if children is not None and not isinstance(children, str):
            stack.append(children)


def _graphs(components) -> list[go.Figure]:
    return [n.figure for n in _walk(components) if isinstance(n, dcc.Graph)]


def test_trends_view(silver_history_df):
    view = trends_view(silver_history_df, "Last 6 months")
    assert not view["is_empty"]
    assert view["direction"] in {"Em alta", "Em queda", "Estável"}
    assert view["pop"]["has_data"]
    assert len(view["pop"]["current_months"]) == 6
    assert set(view["yoy"]["month_name"]) <= {
        "jan",
        "fev",
        "mar",
        "abr",
        "mai",
        "jun",
        "jul",
        "ago",
        "set",
        "out",
        "nov",
        "dez",
    }


def test_watchlist_view_uses_full_history_for_recurring(silver_history_df):
    view = watchlist_view(silver_history_df, "Last 3 months")
    scope = slice_data(silver_history_df, "Last 3 months").df_scope
    assert view["recurring"]["id"].tolist() == get_recurring_merchants(scope)["id"].tolist()
    assert "DEMO STREAMING" in set(view["recurring"]["id"])
    assert view["fixed_cost"] > 0
    assert 0 <= view["uncategorized_pct"] <= 100
    assert view["uncategorized"]["total"].is_monotonic_decreasing


def test_category_view_defaults_to_largest_and_respects_choice(silver_history_df):
    options = category_options(silver_history_df, "All History")
    default = category_view(silver_history_df, "All History")
    assert default["selected"] == options[0][0]
    food = category_view(silver_history_df, "All History", selected="food")
    assert food["selected"] == "food" and food["label"] == "Alimentação"
    assert food["count"] > 0 and food["avg_ticket"] == pytest.approx(food["total"] / food["count"])
    assert food["history"]["year_month"].is_monotonic_increasing
    assert len(food["largest"]) <= 10
    # Unknown selection falls back to the default instead of failing.
    assert (
        category_view(silver_history_df, "All History", selected="bogus")["selected"]
        == options[0][0]
    )


def test_category_view_limited_by_global_category_filter(silver_history_df):
    view = category_view(silver_history_df, "All History", categories=["food", "travel"])
    assert {key for key, _ in view["options"]} == {"food", "travel"}


def test_reports_view(silver_history_df):
    view = reports_view(silver_history_df, "Last 6 months")
    assert view["metrics"]["has_data"]
    assert view["projection"]["future_month"].is_monotonic_increasing
    assert view["invoices"]["year_month"].tolist() == sorted(
        view["invoices"]["year_month"], reverse=True
    )
    net = view["invoices"]["net"].sum()
    assert net == pytest.approx(view["invoices"]["gross"].sum() + view["invoices"]["refunds"].sum())


def test_export_frame(silver_history_df):
    frame = export_frame(silver_history_df, "Last 3 months", ["CARDHOLDER_A"])
    assert not frame.empty
    assert set(frame["titular"]) == {"CARDHOLDER_A"}
    assert "PAGAMENTO FATURA" not in set(frame["estabelecimento"])
    assert export_frame(pd.DataFrame()).empty


@pytest.mark.parametrize("tab", ["trends", "habits", "watchlist", "reports"])
def test_tabs_render_with_data(silver_history_df, tab):
    body = render_tab(tab, silver_history_df, "Last 6 months", None, None)
    assert body
    figures = _graphs(body)
    assert bool(figures) == (tab != "watchlist"), tab  # Atenção is tables only
    for fig in figures:
        for trace in fig.data:
            marker = getattr(getattr(trace, "marker", None), "color", None)
            colors = set(marker) if isinstance(marker, list | tuple) else {marker}
            assert colors - {None} <= set(PALETTE), (tab, trace.name)


@pytest.mark.parametrize("tab", ["trends", "habits", "watchlist", "reports"])
def test_tabs_render_without_data(tab):
    assert render_tab(tab, pd.DataFrame(), None, [], []) is not None


def test_category_tab_render(silver_history_df):
    body, options, value = render_category(silver_history_df, "All History", None, None, None)
    assert value == options[0]["value"]
    assert len(_graphs(body)) == 2
    body, options, value = render_category(pd.DataFrame(), None, None, None, None)
    assert options == [] and value is None


def test_secondary_figures_empty_states():
    assert isinstance(comparison_figure({"has_data": False}), go.Figure)
    assert isinstance(yoy_figure(pd.DataFrame()), go.Figure)
    assert isinstance(limit_figure(pd.DataFrame(), 1000.0), go.Figure)
    assert isinstance(
        category_history_figure(pd.DataFrame(columns=["year_month", "cost"]), "food"), go.Figure
    )


def test_habits_view(silver_history_df):
    view = habits_view(silver_history_df, "Last 6 months")
    assert not view["is_empty"]
    purchases = slice_data(silver_history_df, "Last 6 months").df
    purchases = purchases[purchases["cost"] > 0]
    assert view["total"] == pytest.approx(purchases["cost"].sum())
    assert view["count"] == len(purchases)
    # Every purchase lands in exactly one band / weekday / payment kind.
    assert view["bands"]["band"].tolist() == TICKET_LABELS
    assert view["bands"]["tx"].sum() == view["count"]
    assert view["bands"]["share"].sum() == pytest.approx(100)
    assert view["weekday"]["tx"].sum() == view["count"]
    assert view["weekday"]["day"].tolist()[0] == "Segunda"
    assert view["split"].to_numpy().sum() == pytest.approx(view["total"])
    assert view["holders"].to_numpy().sum() == pytest.approx(view["total"])
    assert set(view["holders"].columns) == {"CARDHOLDER_A", "CARDHOLDER_B"}
    assert 0 < view["installment_share"] < 100
    assert 0 < view["top10_share"] <= 100
    assert 1 <= view["pareto_n"] <= view["merchants"]
    assert habits_view(pd.DataFrame())["is_empty"]


def test_category_month_matrix(silver_history_df):
    sliced = slice_data(silver_history_df, "Last 6 months")
    matrix = category_month_matrix(sliced.df, sliced.months)
    assert list(matrix.columns) == sliced.months
    assert matrix.sum(axis=1).is_monotonic_decreasing
    assert "Alimentação" in matrix.index
    assert category_month_matrix(pd.DataFrame(), []).empty


def test_new_merchants(silver_history_df):
    extra = silver_history_df.iloc[[0]].copy()
    extra[["id", "date", "date_buy", "year_month", "cost"]] = [
        "BRAND NEW SHOP",
        pd.Timestamp("2026-09-05"),
        pd.Timestamp("2026-09-01"),
        "2026-09",
        99.0,
    ]
    df = pd.concat([silver_history_df, extra], ignore_index=True)
    sliced = slice_data(df, "Last 3 months")
    found = new_merchants(sliced.df, sliced.df_scope, sliced.months)
    assert "BRAND NEW SHOP" in set(found["id"])
    assert "DEMO STREAMING" not in set(found["id"])  # billed since the first month
    everything = slice_data(df, "All History")
    assert new_merchants(everything.df, everything.df_scope, everything.months).empty
