"""Plotly figure builders for the dashboard (no Streamlit / Dash imports).

Category bars are coloured per category; other series use `theme.SERIES_COLORS`.
"""

import pandas as pd
import plotly.graph_objects as go

from src.expenses.dashboard.data import DashboardView, month_label
from src.expenses.dashboard.theme import (
    ACCENT,
    AVERAGE,
    COMMITMENT,
    MUTED,
    category_color,
    category_label_color,
    plotly_layout,
)

HOVER_BRL = "%{customdata}<br>R$ %{y:,.2f}<extra></extra>"


def empty_figure(message: str = "Sem dados no período", height: int = 320) -> go.Figure:
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
    monthly = view.monthly
    if monthly.empty:
        return empty_figure(height=height)
    labels = [month_label(m) for m in monthly["year_month"]]
    fig = go.Figure(
        [
            go.Bar(
                x=labels,
                y=monthly["cost"],
                marker_color=ACCENT,
                name="Gasto",
                customdata=labels,
                hovertemplate=HOVER_BRL,
            ),
            go.Scatter(
                x=labels,
                y=monthly["moving_avg"],
                mode="lines",
                line={"color": AVERAGE, "width": 2.5, "dash": "dash"},
                name="Média 3M",
                hovertemplate="Média 3M<br>R$ %{y:,.2f}<extra></extra>",
            ),
        ]
    )
    fig.update_layout(**plotly_layout(height=height), hovermode="x unified")
    return fig


def ranked_bar_figure(
    df: pd.DataFrame,
    label_col: str,
    value_col: str,
    colors: list[str] | None = None,
    height: int = 360,
) -> go.Figure:
    """Horizontal ranking, largest on top; ``colors`` align with ``df`` rows."""
    if df.empty:
        return empty_figure(height=height)
    data = df.assign(_color=colors if colors is not None else ACCENT)
    data = data.sort_values(value_col, ascending=True)
    fig = go.Figure(
        go.Bar(
            x=data[value_col],
            y=data[label_col],
            orientation="h",
            marker_color=data["_color"].tolist(),
            text=[f"R$ {v:,.0f}" for v in data[value_col]],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}<br>R$ %{x:,.2f}<extra></extra>",
        )
    )
    layout = plotly_layout(height=height)
    layout["margin"] = {"l": 8, "r": 56, "t": 8, "b": 8}
    layout["xaxis"] = {"visible": False}
    layout["yaxis"] = {"showgrid": False, "title": None, "automargin": True, "ticksuffix": "  "}
    fig.update_layout(**layout)
    return fig


def commitments_figure(view: DashboardView, height: int = 360) -> go.Figure:
    """Installments already contracted, per future invoice month."""
    data = view.commitments
    if data.empty:
        return empty_figure("Nenhuma parcela futura", height=height)
    labels = [month_label(m) for m in data["future_month"]]
    fig = go.Figure(
        go.Bar(
            x=labels,
            y=data["cost"],
            marker_color=COMMITMENT,
            customdata=labels,
            hovertemplate=HOVER_BRL,
        )
    )
    fig.update_layout(**plotly_layout(height=height))
    return fig


def all_figures(view: DashboardView) -> dict[str, go.Figure]:
    return {
        "monthly": monthly_figure(view),
        "categories": ranked_bar_figure(
            view.by_category,
            "category_label",
            "cost",
            [category_label_color(c) for c in view.by_category["category_label"]],
        ),
        "merchants": ranked_bar_figure(
            view.top_merchants,
            "id",
            "total_spent",
            [category_color(c) for c in view.top_merchants.get("category", [])] or None,
        ),
        "commitments": commitments_figure(view),
    }
