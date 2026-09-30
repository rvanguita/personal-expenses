import pandas as pd
import plotly.graph_objects as go

import expenses_streamlit.charts as charts
from expenses_streamlit.charts import add_total_line_trace, build_ranked_bar_chart


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


def test_chart_context_overrides_theme_and_amounts():
    df = pd.DataFrame({"id": ["A", "B"], "cost": [1.0, 2.0]})
    with charts.chart_context(theme_base="light", hide_amounts=True):
        fig = build_ranked_bar_chart(df, "id", "cost")
    assert fig.layout.font.color == "#1F2933"
    assert not fig.data[0].text


def test_theme_helpers_follow_the_active_base():
    with charts.chart_context(theme_base="light"):
        assert charts._is_light_theme() is True
        assert charts.grid_color() == "#D0D7DE"
        assert charts.axis_text_color() == "#1F2933"
        assert charts.total_line_color() == "#1F2933"
    with charts.chart_context(theme_base="dark"):
        assert charts._is_light_theme() is False
        assert charts.grid_color() == charts.GRID_COLOR
        assert charts.axis_text_color() == charts.AXIS_TEXT_COLOR
        assert charts.total_line_color() == "#FFFFFF"


def test_apply_chart_theme_money_axis_and_legend_modes():
    with charts.chart_context(theme_base="dark"):
        fig = charts.apply_chart_theme(go.Figure(), height=300, legend="top")
    assert fig.layout.height == 300
    assert fig.layout.yaxis.tickprefix == "R$ "
    assert fig.layout.legend.orientation == "h"
    hidden = charts.apply_chart_theme(go.Figure(), legend="hidden")
    assert hidden.layout.showlegend is False
    bottom = charts.apply_chart_theme(go.Figure(), legend="bottom")
    assert bottom.layout.margin.b == 130


def test_budget_status_color():
    assert charts.budget_status_color(True) == charts.STATUS_COLORS["critical"]
    assert charts.budget_status_color(False) == charts.STATUS_COLORS["good"]
