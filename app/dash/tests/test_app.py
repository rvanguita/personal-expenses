"""Dash app: layout builds and the callback body renders on synthetic data (no DB)."""

import pandas as pd
import plotly.graph_objects as go
from dash import Dash

from expenses_dash import create_app, update_dashboard
from expenses_dash.callbacks import register_callbacks
from expenses_dash.layout import FIGURE_IDS


def _ids(component) -> set[str]:
    found, stack = set(), [component]
    while stack:
        node = stack.pop()
        if getattr(node, "id", None):
            found.add(node.id)
        children = getattr(node, "children", None)
        if isinstance(children, list | tuple):
            stack.extend(children)
        elif children is not None and hasattr(children, "children"):
            stack.append(children)
    return found


def test_layout_has_filters_kpis_and_graphs(silver_history_df):
    app = create_app(loader=lambda: silver_history_df)
    ids = _ids(app.layout())
    assert {"f-period", "f-holders", "f-categories", "subtitle", "kpis", "largest"} <= ids
    assert {f"fig-{name}" for name in FIGURE_IDS} <= ids
    assert {
        "tabs",
        "trends-content",
        "habits-content",
        "watchlist-content",
        "category-content",
        "f-category-detail",
        "reports-content",
        "btn-csv",
        "download-csv",
    } <= ids


def test_layout_builds_without_data():
    app = create_app(loader=pd.DataFrame)
    assert "f-period" in _ids(app.layout())


def test_update_dashboard_with_data(silver_history_df):
    subtitle, kpis, table, *figures = update_dashboard(
        silver_history_df, "Last 6 months", None, None
    )
    assert "Últimos 6 meses" in subtitle and "última fatura" in subtitle
    assert len(kpis) == 4
    assert table != []
    assert len(figures) == len(FIGURE_IDS)
    assert all(isinstance(fig, go.Figure) and fig.data for fig in figures)


def test_update_dashboard_empty():
    _subtitle, kpis, table, *figures = update_dashboard(pd.DataFrame(), None, [], [])
    assert len(kpis) == 1 and table == []
    assert all(isinstance(fig, go.Figure) for fig in figures)


def test_register_callbacks_wires_every_tab(silver_history_df):
    app = Dash(__name__)
    register_callbacks(app, lambda: silver_history_df)
    outputs = " ".join(app.callback_map)
    for target in (
        "subtitle.children",
        "fig-monthly.figure",
        "trends-content.children",
        "habits-content.children",
        "watchlist-content.children",
        "reports-content.children",
        "category-content.children",
        "download-csv.data",
    ):
        assert target in outputs, target
