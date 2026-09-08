import pandas as pd
import plotly.graph_objects as go

import src.expenses.ui.charts as charts
from src.expenses.ui.charts import add_total_line_trace, build_ranked_bar_chart


def test_add_total_line_trace_has_no_on_plot_labels():
    fig = add_total_line_trace(go.Figure(), ["2026-07", "2026-08"], [10.0, 20.0], name="Total")
    trace = fig.data[-1]
    assert trace.mode == "lines+markers"
    assert not trace.text
    assert list(trace.y) == [10.0, 20.0]


def test_add_total_line_trace_point_labels():
    fig = add_total_line_trace(go.Figure(), ["2026-07", "2026-08"], [10.0, 20.0], point_labels=True)
    trace = fig.data[-1]
    assert trace.mode == "lines+markers+text"
    assert list(trace.text) == ["R$ 10.00", "R$ 20.00"]


def _ranked_df():
    return pd.DataFrame({"id": ["A", "B", "C"], "cost": [1.0, 2.0, 3.0]})


def test_build_ranked_bar_chart_labels_bars_by_default(monkeypatch):
    monkeypatch.setattr(charts, "amounts_hidden", lambda: False)
    fig = build_ranked_bar_chart(_ranked_df(), "id", "cost")
    assert list(fig.data[0].text) == ["R$ 1.00", "R$ 2.00", "R$ 3.00"]


def test_build_ranked_bar_chart_drops_labels_when_amounts_hidden(monkeypatch):
    monkeypatch.setattr(charts, "amounts_hidden", lambda: True)
    fig = build_ranked_bar_chart(_ranked_df(), "id", "cost")
    assert not fig.data[0].text
