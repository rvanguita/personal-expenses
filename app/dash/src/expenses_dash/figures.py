"""Plotly figure builders for the Dash dashboard. Only `theme.PALETTE` colours are used."""

import pandas as pd
import plotly.graph_objects as go

from expenses_dash.data import DashboardView, month_label
from expenses_dash.fmt import brl
from expenses_dash.theme import (
    ACCENT,
    AVERAGE,
    CARD,
    COMMITMENT,
    LEGEND_TOP,
    LIMIT,
    MUTED,
    PREVIOUS,
    TEXT,
    category_color,
    plotly_layout,
)

_HOVER_MONTH = "%{customdata}<br>R$ %{y:,.2f}<extra></extra>"


def empty_figure(message: str = "No data for this period", height: int = 320) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        **plotly_layout(height=height),
        annotations=[
            {
                "text": message,
                "showarrow": False,
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "font": {"color": MUTED, "size": 13},
            }
        ],
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def monthly_figure(view: DashboardView, height: int = 320) -> go.Figure:
    """Net spend per invoice month (bars) with the trailing 3-month average (dashed line)."""
    if view.monthly.empty:
        return empty_figure(height=height)
    labels = [month_label(m) for m in view.monthly["year_month"]]
    fig = go.Figure(
        [
            go.Bar(
                x=labels,
                y=view.monthly["cost"],
                name="Spend",
                marker_color=ACCENT,
                customdata=labels,
                hovertemplate=_HOVER_MONTH,
            ),
            go.Scatter(
                x=labels,
                y=view.monthly["moving_avg"],
                name="3-month average",
                mode="lines",
                line={"color": AVERAGE, "width": 2.5, "dash": "dash"},
                hovertemplate="3-month average<br>R$ %{y:,.2f}<extra></extra>",
            ),
        ]
    )
    fig.update_layout(**plotly_layout(height=height), hovermode="x unified")
    return fig


def ranked_bar_figure(
    df: pd.DataFrame, label_col: str, value_col: str, colors: list[str], height: int = 360
) -> go.Figure:
    """Horizontal ranking, largest on top; ``colors`` are aligned with ``df`` rows."""
    if df.empty:
        return empty_figure(height=height)
    data = df.assign(_color=colors).sort_values(value_col, ascending=True)
    fig = go.Figure(
        go.Bar(
            x=data[value_col],
            y=data[label_col],
            orientation="h",
            marker_color=data["_color"].tolist(),
            text=[brl(v, 0) for v in data[value_col]],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}<br>R$ %{x:,.2f}<extra></extra>",
        )
    )
    layout = plotly_layout(height=height)
    layout["margin"] = {"l": 8, "r": 60, "t": 8, "b": 8}
    layout["xaxis"] = {"visible": False}
    layout["yaxis"] = {"showgrid": False, "title": None, "automargin": True, "ticksuffix": "  "}
    fig.update_layout(**layout)
    return fig


def category_figure(view: DashboardView) -> go.Figure:
    df = view.by_category
    return ranked_bar_figure(
        df, "category_label", "cost", [category_color(c) for c in df["category"]]
    )


def merchants_figure(view: DashboardView) -> go.Figure:
    df = view.top_merchants
    colors = [category_color(c) for c in df.get("category", pd.Series(index=df.index))]
    return ranked_bar_figure(df, "id", "total_spent", colors)


def commitments_figure(view: DashboardView, height: int = 360) -> go.Figure:
    """Installments already contracted, per future invoice month."""
    if view.commitments.empty:
        return empty_figure("No future installments", height=height)
    labels = [month_label(m) for m in view.commitments["future_month"]]
    fig = go.Figure(
        go.Bar(
            x=labels,
            y=view.commitments["cost"],
            marker_color=COMMITMENT,
            customdata=labels,
            hovertemplate=_HOVER_MONTH,
        )
    )
    fig.update_layout(**plotly_layout(height=height))
    return fig


def comparison_figure(pop: dict, top_n: int = 10, height: int = 380) -> go.Figure:
    """Top categories: selected period vs the same number of months right before it."""
    by_cat = pop.get("by_category", pd.DataFrame())
    if not pop.get("has_data") or by_cat.empty:
        return empty_figure("No previous period to compare", height=height)
    data = by_cat.head(top_n).iloc[::-1]
    prev, cur = pop["previous_months"], pop["current_months"]
    fig = go.Figure(
        [
            go.Bar(
                y=data["category_label"],
                x=data["previous"],
                orientation="h",
                name=f"Previous ({month_label(prev[0])}–{month_label(prev[-1])})",
                marker_color=PREVIOUS,
                hovertemplate="%{y}<br>R$ %{x:,.2f}<extra>Previous</extra>",
            ),
            go.Bar(
                y=data["category_label"],
                x=data["current"],
                orientation="h",
                name=f"Current ({month_label(cur[0])}–{month_label(cur[-1])})",
                marker_color=ACCENT,
                hovertemplate="%{y}<br>R$ %{x:,.2f}<extra>Current</extra>",
            ),
        ]
    )
    layout = plotly_layout(height=height, showlegend=True, legend=LEGEND_TOP, barmode="group")
    layout["margin"] = {"l": 8, "r": 8, "t": 30, "b": 8}
    layout["bargap"] = 0.25
    layout["xaxis"] = {**layout["yaxis"]}
    layout["yaxis"] = {"showgrid": False, "title": None, "automargin": True, "ticksuffix": "  "}
    fig.update_layout(**layout)
    return fig


def yoy_figure(yoy: pd.DataFrame, height: int = 320) -> go.Figure:
    """Same calendar months, previous year vs current year."""
    if yoy.empty:
        return empty_figure("Less than two years of history", height=height)
    prev_year, cur_year = int(yoy["previous_year"].iloc[0]), int(yoy["current_year"].iloc[0])
    fig = go.Figure(
        [
            go.Bar(
                x=yoy["month_name"],
                y=yoy["previous_val"],
                name=str(prev_year),
                marker_color=PREVIOUS,
                hovertemplate=f"%{{x}}/{prev_year}<br>R$ %{{y:,.2f}}<extra></extra>",
            ),
            go.Bar(
                x=yoy["month_name"],
                y=yoy["current_val"],
                name=str(cur_year),
                marker_color=ACCENT,
                hovertemplate=f"%{{x}}/{cur_year}<br>R$ %{{y:,.2f}}<extra></extra>",
            ),
        ]
    )
    layout = plotly_layout(height=height, showlegend=True, legend=LEGEND_TOP, barmode="group")
    layout["margin"] = {"l": 8, "r": 8, "t": 30, "b": 8}
    layout["bargap"] = 0.25
    fig.update_layout(**layout)
    return fig


def category_history_figure(history: pd.DataFrame, key: str, height: int = 320) -> go.Figure:
    """One category's net spend per invoice month, in the category's colour."""
    if history.empty or not history["cost"].any():
        return empty_figure(height=height)
    labels = [month_label(m) for m in history["year_month"]]
    fig = go.Figure(
        go.Bar(
            x=labels,
            y=history["cost"],
            marker_color=category_color(key),
            customdata=labels,
            hovertemplate=_HOVER_MONTH,
        )
    )
    fig.update_layout(**plotly_layout(height=height))
    return fig


def limit_figure(projection: pd.DataFrame, limit: float, height: int = 340) -> go.Figure:
    """Installments already due per future month against the reference limit (dashed line)."""
    if projection.empty:
        return empty_figure("No future installments", height=height)
    labels = [month_label(m) for m in projection["future_month"]]
    colors = [LIMIT if v > limit else COMMITMENT for v in projection["cost"]]
    fig = go.Figure(
        go.Bar(
            x=labels,
            y=projection["cost"],
            marker_color=colors,
            customdata=labels,
            hovertemplate=_HOVER_MONTH,
        )
    )
    fig.add_hline(
        y=limit,
        line={"color": LIMIT, "width": 1.5, "dash": "dash"},
        annotation_text=f"Limit {brl(limit, 0)}",
        annotation_position="top right",
        annotation_font={"color": LIMIT, "size": 11},
    )
    fig.update_layout(**plotly_layout(height=height))
    return fig


def split_figure(split: pd.DataFrame, height: int = 320) -> go.Figure:
    """Single-payment vs installment purchases per invoice month (stacked)."""
    if split.empty or not split.to_numpy().any():
        return empty_figure(height=height)
    labels = [month_label(m) for m in split.index]
    fig = go.Figure(
        [
            go.Bar(
                x=labels,
                y=split[kind],
                name=kind,
                marker_color=color,
                hovertemplate=f"{kind}<br>R$ %{{y:,.2f}}<extra></extra>",
            )
            for kind, color in (("Single payment", ACCENT), ("Installments", COMMITMENT))
        ]
    )
    legend = {**LEGEND_TOP, "traceorder": "normal"}
    layout = plotly_layout(height=height, showlegend=True, legend=legend, barmode="stack")
    layout["margin"] = {"l": 8, "r": 8, "t": 30, "b": 8}
    fig.update_layout(**layout, hovermode="x unified")
    return fig


def bands_figure(bands: pd.DataFrame, height: int = 320) -> go.Figure:
    """Spend per purchase-size band; the label shows how many purchases fall in each band."""
    if bands.empty or not bands["tx"].any():
        return empty_figure(height=height)
    fig = go.Figure(
        go.Bar(
            x=list(bands["band"]),
            y=bands["total"],
            marker_color=ACCENT,
            text=[f"{int(n)} purchases" for n in bands["tx"]],
            textposition="outside",
            cliponaxis=False,
            customdata=bands["share"],
            hovertemplate="Purchases of R$ %{x}<br>R$ %{y:,.2f} · %{customdata:.1f}% of spend"
            "<br>%{text}<extra></extra>",
        )
    )
    layout = plotly_layout(height=height)
    layout["margin"] = {"l": 8, "r": 8, "t": 24, "b": 8}
    layout["xaxis"] = {**layout["xaxis"], "tickangle": 0, "title": "purchase amount (R$)"}
    fig.update_layout(**layout)
    return fig


def weekday_figure(weekday: pd.DataFrame, height: int = 320) -> go.Figure:
    """Spend per day of the week (purchase date), busiest day highlighted."""
    if weekday.empty or not weekday["tx"].any():
        return empty_figure(height=height)
    peak = weekday["total"].idxmax()
    colors = [AVERAGE if i == peak else ACCENT for i in weekday.index]
    fig = go.Figure(
        go.Bar(
            x=weekday["day"],
            y=weekday["total"],
            marker_color=colors,
            customdata=weekday[["tx", "avg_ticket"]].to_numpy(),
            hovertemplate="%{x}<br>R$ %{y:,.2f}<br>%{customdata[0]} purchases · average ticket "
            "R$ %{customdata[1]:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(**plotly_layout(height=height))
    return fig


_HOLDER_COLORS = (ACCENT, AVERAGE, COMMITMENT, PREVIOUS)


def holders_figure(holders: pd.DataFrame, height: int = 320) -> go.Figure:
    """Purchases per cardholder and invoice month (grouped bars)."""
    if holders.empty or not holders.to_numpy().any():
        return empty_figure(height=height)
    labels = [month_label(m) for m in holders.index]
    fig = go.Figure(
        [
            go.Bar(
                x=labels,
                y=holders[name],
                name=str(name),
                marker_color=_HOLDER_COLORS[i % len(_HOLDER_COLORS)],
                hovertemplate=f"{name}<br>R$ %{{y:,.2f}}<extra></extra>",
            )
            for i, name in enumerate(holders.columns)
        ]
    )
    layout = plotly_layout(height=height, showlegend=True, legend=LEGEND_TOP, barmode="group")
    layout["margin"] = {"l": 8, "r": 8, "t": 30, "b": 8}
    layout["bargap"] = 0.25
    fig.update_layout(**layout)
    return fig


def heatmap_figure(matrix: pd.DataFrame, height: int | None = None) -> go.Figure:
    """Category × month spend; darker = less, brighter blue = more."""
    if matrix.empty:
        return empty_figure()
    height = height or 80 + 30 * len(matrix)
    months = [month_label(m) for m in matrix.columns]
    fig = go.Figure(
        go.Heatmap(
            z=matrix.to_numpy(),
            x=months,
            y=list(matrix.index),
            colorscale=[[0.0, CARD], [0.5, "#2F5F8F"], [1.0, ACCENT]],
            xgap=3,
            ygap=3,
            showscale=False,
            text=[[brl(v, 0) for v in row] for row in matrix.to_numpy()],
            texttemplate="%{text}",
            textfont={"size": 10, "color": TEXT},
            hovertemplate="%{y} · %{x}<br>R$ %{z:,.2f}<extra></extra>",
        )
    )
    layout = plotly_layout(height=height)
    layout["xaxis"] = {"side": "top", "showgrid": False, "title": None}
    layout["yaxis"] = {
        "autorange": "reversed",
        "showgrid": False,
        "automargin": True,
        "title": None,
        "ticksuffix": "  ",
    }
    layout["margin"] = {"l": 8, "r": 8, "t": 28, "b": 8}
    fig.update_layout(**layout)
    return fig
