"""Dash frontend: layout builds and the callback body renders on synthetic data (no DB)."""

import pandas as pd
import plotly.graph_objects as go

import dash_app


def _ids(component) -> set[str]:
    found = set()
    stack = [component]
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
    app = dash_app.create_app(loader=lambda: silver_history_df)
    ids = _ids(app.layout)
    assert {"f-period", "f-holders", "f-categories", "kpis", "largest", "subtitle"} <= ids
    assert {f"fig-{k}" for k in dash_app.FIGURE_IDS} <= ids


def test_update_dashboard_with_data(silver_history_df):
    subtitle, kpis, table, *figures = dash_app.update_dashboard(
        silver_history_df, "Last 6 months", None, None
    )
    assert "Últimos 6 meses" in subtitle
    assert len(kpis) == 4
    assert table is not None and table != []
    assert len(figures) == 4
    assert all(isinstance(f, go.Figure) and f.data for f in figures)


def test_update_dashboard_empty():
    subtitle, kpis, table, *figures = dash_app.update_dashboard(pd.DataFrame(), None, [], [])
    assert len(kpis) == 1 and table == []
    assert all(isinstance(f, go.Figure) for f in figures)
