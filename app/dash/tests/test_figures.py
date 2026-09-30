"""Every Dash figure builder (expenses_dash.figures): data, empty state and palette."""

import pandas as pd
import plotly.graph_objects as go
import pytest

from expenses_dash.analyses import category_month_matrix, habits_view
from expenses_dash.data import build_view, slice_data
from expenses_dash.figures import (
    bands_figure,
    empty_figure,
    heatmap_figure,
    holders_figure,
    ranked_bar_figure,
    split_figure,
    weekday_figure,
)
from expenses_dash.theme import ACCENT, AVERAGE, COMMITMENT, PALETTE, category_color, plotly_layout


@pytest.fixture
def habits(silver_history_df):
    return habits_view(silver_history_df, "Last 6 months")


def test_empty_figure():
    fig = empty_figure("Nada aqui", height=200)
    assert fig.layout.annotations[0].text == "Nada aqui"
    assert fig.layout.height == 200 and not fig.data


def test_ranked_bar_figure_orders_and_colors():
    df = pd.DataFrame({"name": ["a", "b", "c"], "v": [2.0, 3.0, 1.0]})
    fig = ranked_bar_figure(df, "name", "v", ["#111111", "#222222", "#333333"])
    bar = fig.data[0]
    assert list(bar.y) == ["c", "a", "b"]  # largest last = drawn on top
    assert list(bar.marker.color) == ["#333333", "#111111", "#222222"]
    assert list(bar.text) == ["R$ 1", "R$ 2", "R$ 3"]
    assert ranked_bar_figure(df.iloc[0:0], "name", "v", []).layout.annotations


def test_split_figure(habits):
    fig = split_figure(habits["split"])
    assert [t.name for t in fig.data] == ["À vista", "Parcelado"]
    assert [t.marker.color for t in fig.data] == [ACCENT, COMMITMENT]
    assert split_figure(habits["split"] * 0).layout.annotations


def test_bands_figure(habits):
    fig = bands_figure(habits["bands"])
    assert list(fig.data[0].x) == list(habits["bands"]["band"])
    assert fig.data[0].text[0].endswith("compras")
    assert bands_figure(habits["bands"].assign(tx=0)).layout.annotations


def test_weekday_figure_highlights_peak(habits):
    fig = weekday_figure(habits["weekday"])
    colors = list(fig.data[0].marker.color)
    assert colors.count(AVERAGE) == 1
    assert colors.index(AVERAGE) == habits["weekday"]["total"].idxmax()
    assert weekday_figure(habits["weekday"].assign(tx=0)).layout.annotations


def test_holders_figure(habits):
    fig = holders_figure(habits["holders"])
    assert [t.name for t in fig.data] == list(habits["holders"].columns)
    assert holders_figure(pd.DataFrame()).layout.annotations


def test_heatmap_figure(silver_history_df):
    sliced = slice_data(silver_history_df, "Last 6 months")
    matrix = category_month_matrix(sliced.df, sliced.months)
    fig = heatmap_figure(matrix)
    assert fig.data[0].type == "heatmap"
    assert list(fig.data[0].y) == list(matrix.index)
    assert fig.layout.height == 80 + 30 * len(matrix)
    assert heatmap_figure(pd.DataFrame()).layout.annotations


def test_theme_helpers():
    assert category_color("food") == "#FF9800"
    assert category_color("unknown") == category_color("not_found")
    layout = plotly_layout(height=123, showlegend=True)
    assert layout["height"] == 123 and layout["showlegend"] is True
    assert layout["separators"] == ",."
    assert layout["yaxis"]["tickprefix"] == "R$ "


def test_overview_figures_stay_in_palette(silver_history_df):
    from expenses_dash.figures import category_figure, commitments_figure, merchants_figure

    view = build_view(silver_history_df, "All History")
    for fig in (category_figure(view), merchants_figure(view), commitments_figure(view)):
        colors = fig.data[0].marker.color
        colors = set(colors) if isinstance(colors, list | tuple) else {colors}
        assert colors <= set(PALETTE)
    assert isinstance(empty_figure(), go.Figure)
