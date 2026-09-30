"""Every Streamlit figure builder: a themed figure with data, ``None`` without."""

import pandas as pd
import plotly.graph_objects as go
import pytest

from expenses.analytics import (
    get_future_installments_details,
    get_future_installments_projection,
    get_moving_average,
    get_period_over_period_comparison,
    get_year_over_year_comparison,
)
from expenses_streamlit.figures import (
    build_budget_vs_limit_figure,
    build_category_distribution_figure,
    build_category_monthly_figure,
    build_future_by_category_figure,
    build_period_comparison_figure,
    build_top_merchants_figure,
    build_trend_figure,
    build_yoy_figure,
)


@pytest.fixture
def expenses_df(silver_history_df):
    return silver_history_df[~silver_history_df["is_payment"]]


def test_build_category_distribution_figure(expenses_df):
    fig = build_category_distribution_figure(expenses_df)
    assert isinstance(fig, go.Figure)
    assert set(fig.data[0].y) <= set(expenses_df["category_label"])
    assert build_category_distribution_figure(expenses_df.iloc[0:0]) is None


def test_build_top_merchants_figure(expenses_df):
    fig = build_top_merchants_figure(expenses_df, top_n=5)
    assert len(fig.data[0].y) == 5
    assert build_top_merchants_figure(expenses_df.iloc[0:0]) is None


def test_build_category_monthly_figure(expenses_df):
    food = expenses_df[expenses_df["category"] == "food"]
    fig = build_category_monthly_figure(food, "Food & Dining", "#FF9800")
    assert isinstance(fig, go.Figure) and fig.data
    assert build_category_monthly_figure(food.iloc[0:0], "Food & Dining", "#FF9800") is None


def test_build_trend_figure(expenses_df):
    fig = build_trend_figure(get_moving_average(expenses_df))
    assert [t.type for t in fig.data] == ["bar", "scatter"]
    assert build_trend_figure(get_moving_average(expenses_df).head(1)) is None


def test_build_period_comparison_figure(silver_history_df):
    months = sorted(silver_history_df["year_month"].unique())[-3:]
    fig = build_period_comparison_figure(
        get_period_over_period_comparison(silver_history_df, months)
    )
    assert len(fig.data) == 2
    # No earlier months to compare against -> empty by_category -> no figure.
    first = sorted(silver_history_df["year_month"].unique())[:1]
    assert (
        build_period_comparison_figure(get_period_over_period_comparison(silver_history_df, first))
        is None
    )


def test_build_yoy_figure(silver_history_df):
    fig = build_yoy_figure(get_year_over_year_comparison(silver_history_df))
    assert len(fig.data) == 2
    assert build_yoy_figure(pd.DataFrame()) is None


def test_build_budget_vs_limit_figure(silver_history_df):
    projection = get_future_installments_projection(silver_history_df)
    fig = build_budget_vs_limit_figure(projection, 1000.0)
    assert isinstance(fig, go.Figure) and fig.data
    assert build_budget_vs_limit_figure(projection.iloc[0:0], 1000.0) is None


def test_build_future_by_category_figure(silver_history_df):
    details = get_future_installments_details(silver_history_df)
    fig = build_future_by_category_figure(details)
    assert isinstance(fig, go.Figure) and fig.data
    assert build_future_by_category_figure(details.iloc[0:0]) is None
