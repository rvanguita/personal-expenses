"""Framework-agnostic Plotly figure builders used by the Streamlit frontend.

Every builder takes already-filtered frames (as produced by ``analytics`` / ``filters``) and
returns a themed ``go.Figure`` — or ``None`` when there is nothing to plot. Theme and
hide-amounts handling come from ``ui.charts`` (see ``charts.chart_context``).
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.streamlit.ui.charts import (
    EMPHASIS_ACCENT,
    EMPHASIS_MUTED,
    add_total_line_trace,
    amounts_hidden,
    apply_chart_theme,
    budget_status_color,
    build_ranked_bar_chart,
)
from src.expenses.analytics import get_top_merchants
from src.expenses.config import (
    CATEGORY_COLOR_MAP,
    format_currency_br,
    get_category_color,
)


def build_category_distribution_figure(
    df_expenses: pd.DataFrame, height: int = 420
) -> go.Figure | None:
    """Ranked bars of positive spend per category."""
    cat_summary = (
        df_expenses[df_expenses["cost"] > 0]
        .groupby(["category", "category_label"])["cost"]
        .sum()
        .reset_index()
    )
    if cat_summary.empty:
        return None
    return build_ranked_bar_chart(
        cat_summary, "category_label", "cost", color_map=CATEGORY_COLOR_MAP, height=height
    )


def build_top_merchants_figure(
    df_expenses: pd.DataFrame, top_n: int = 10, height: int = 390
) -> go.Figure | None:
    """Ranked bars of the top merchants, each colored by its dominant category."""
    top_merchants = get_top_merchants(df_expenses, top_n=top_n)
    if top_merchants.empty:
        return None
    merchant_color_map = (
        {row["id"]: get_category_color(row["category"]) for _, row in top_merchants.iterrows()}
        if "category" in top_merchants.columns
        else None
    )
    return build_ranked_bar_chart(
        top_merchants, "id", "total_spent", color_map=merchant_color_map, height=height
    )


def build_category_monthly_figure(
    df_cat_exp: pd.DataFrame, category_label: str, category_color: str, height: int = 350
) -> go.Figure | None:
    """Monthly spend line for one category."""
    cat_monthly = (
        df_cat_exp.groupby("year_month")["cost"]
        .sum()
        .reset_index()
        .sort_values(by="year_month", ascending=True)
    )
    if cat_monthly.empty:
        return None
    fig = go.Figure()
    add_total_line_trace(
        fig,
        cat_monthly["year_month"],
        cat_monthly["cost"],
        name=category_label,
        color=category_color,
        dash="solid",
    )
    apply_chart_theme(fig, height=height, legend="hidden")
    fig.update_layout(
        xaxis={
            "type": "category",
            "categoryorder": "array",
            "categoryarray": cat_monthly["year_month"].tolist(),
            "title": "",
        },
        yaxis={"range": [0, float(cat_monthly["cost"].max()) * 1.25]},
    )
    return fig


def build_trend_figure(ma_df: pd.DataFrame, height: int = 340) -> go.Figure | None:
    """Net monthly spend (bars) with its 3-month moving average (dashed line); needs 2+ months."""
    if len(ma_df) < 2:
        return None
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=ma_df["year_month"],
            y=ma_df["cost"],
            name="Net spending",
            marker_color=EMPHASIS_ACCENT,
            hovertemplate="%{x}<br>R$ %{y:,.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=ma_df["year_month"],
            y=ma_df["moving_avg"],
            mode="lines",
            name="3-month average",
            line={"color": "#FFB74D", "width": 2.5, "dash": "dash"},
            hovertemplate="3-month average<br>R$ %{y:,.2f}<extra></extra>",
        )
    )
    apply_chart_theme(fig, height=height, legend="top")
    fig.update_layout(
        bargap=0.35,
        xaxis={"type": "category", "title": ""},
    )
    return fig


def build_period_comparison_figure(pop: dict, height: int = 360) -> go.Figure | None:
    """Current vs previous period grouped bars per category (top 10)."""
    by_cat = pop["by_category"].head(10)
    if by_cat.empty:
        return None
    prev_range = f"{pop['previous_months'][0]} → {pop['previous_months'][-1]}"
    cur_range = f"{pop['current_months'][0]} → {pop['current_months'][-1]}"
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=by_cat["category_label"],
            y=by_cat["previous"],
            name=f"Previous ({prev_range})",
            marker_color=EMPHASIS_MUTED,
        )
    )
    fig.add_trace(
        go.Bar(
            x=by_cat["category_label"],
            y=by_cat["current"],
            name=f"Current ({cur_range})",
            marker_color=EMPHASIS_ACCENT,
        )
    )
    fig.update_layout(barmode="group")
    apply_chart_theme(fig, height=height, legend="top")
    fig.update_layout(xaxis={"title": "", "tickangle": -30})
    return fig


def build_yoy_figure(yoy: pd.DataFrame, height: int = 360) -> go.Figure | None:
    """Same-month spend, previous vs current year."""
    if yoy.empty:
        return None
    cur_year = int(yoy["current_year"].iloc[0])
    prev_year = int(yoy["previous_year"].iloc[0])
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=yoy["month_name"],
            y=yoy["previous_val"],
            name=str(prev_year),
            marker_color=EMPHASIS_MUTED,
        )
    )
    fig.add_trace(
        go.Bar(
            x=yoy["month_name"],
            y=yoy["current_val"],
            name=str(cur_year),
            marker_color=EMPHASIS_ACCENT,
        )
    )
    fig.update_layout(barmode="group")
    apply_chart_theme(fig, height=height, legend="top")
    return fig


def build_budget_vs_limit_figure(
    df_projection: pd.DataFrame, ref_limit: float, height: int = 380
) -> go.Figure | None:
    """Monthly locked installment budget against the reference limit line."""
    if df_projection.empty:
        return None
    # The projection is per (month, category); the budget line compares monthly totals.
    df_plot = df_projection.groupby("future_month", as_index=False)["cost"].sum()
    within_label = f"Within {format_currency_br(ref_limit)}"
    over_label = f"Over {format_currency_br(ref_limit)}"
    df_plot["status"] = df_plot["cost"].apply(
        lambda val: over_label if val > ref_limit else within_label
    )
    y_headroom = max(ref_limit, float(df_plot["cost"].max())) * 1.28

    fig = px.bar(
        df_plot,
        x="future_month",
        y="cost",
        text=None if amounts_hidden() else [format_currency_br(v) for v in df_plot["cost"]],
        labels={
            "cost": "Committed Amount (R$)",
            "future_month": "Future Month",
            "status": "Budget Status",
        },
        color="status",
        color_discrete_map={
            within_label: budget_status_color(False),
            over_label: budget_status_color(True),
        },
    )
    fig.update_traces(textposition="outside", cliponaxis=False, textfont={"size": 11})
    # The limit line is labelled through the legend: an on-plot annotation collides with the
    # value labels of bars sitting near the line.
    fig.add_hline(
        y=ref_limit, line_dash="dash", line_color=budget_status_color(True), line_width=2.5
    )
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="lines",
            line={"color": budget_status_color(True), "dash": "dash", "width": 2.5},
            name="Reference limit"
            if amounts_hidden()
            else f"Reference limit ({format_currency_br(ref_limit)})",
        )
    )
    apply_chart_theme(fig, height=height, legend="bottom")
    fig.update_layout(
        xaxis={"type": "category", "title": ""},
        yaxis={"range": [0, y_headroom]},
    )
    return fig


def build_future_by_category_figure(
    df_details: pd.DataFrame, height: int = 380
) -> go.Figure | None:
    """Future installment commitments stacked by category with a total line."""
    if df_details.empty:
        return None
    df_cat_future = (
        df_details.groupby(["future_month", "category_label", "category"])["cost"]
        .sum()
        .reset_index()
    )
    future_totals = df_details.groupby("future_month")["cost"].sum().reset_index()
    max_future_total = float(future_totals["cost"].max()) if not future_totals.empty else 100.0

    fig = px.bar(
        df_cat_future,
        x="future_month",
        y="cost",
        color="category_label",
        color_discrete_map=CATEGORY_COLOR_MAP,
        labels={
            "cost": "Amount (R$)",
            "future_month": "Future Month",
            "category_label": "Category",
        },
    )
    fig.update_layout(barmode="stack")
    add_total_line_trace(fig, future_totals["future_month"], future_totals["cost"], name="Total")
    apply_chart_theme(fig, height=height, legend="bottom")
    fig.update_layout(
        xaxis={"type": "category", "title": ""},
        yaxis={"range": [0, max_future_total * 1.25]},
    )
    return fig
