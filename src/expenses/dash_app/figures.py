"""Plotly figure builders for the Dash dashboard. Only `theme.PALETTE` colours are used."""

import pandas as pd
import plotly.graph_objects as go

from src.expenses.dash_app.data import DashboardView, month_label
from src.expenses.dash_app.theme import (
    ACCENT,
    AVERAGE,
    COMMITMENT,
    LEGEND_TOP,
    LIMIT,
    MUTED,
    PREVIOUS,
    category_color,
    plotly_layout,
)

_HOVER_MONTH = "%{customdata}<br>R$ %{y:,.2f}<extra></extra>"


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
    if view.monthly.empty:
        return empty_figure(height=height)
    labels = [month_label(m) for m in view.monthly["year_month"]]
    fig = go.Figure(
        [
            go.Bar(
                x=labels,
                y=view.monthly["cost"],
                name="Gasto",
                marker_color=ACCENT,
                customdata=labels,
                hovertemplate=_HOVER_MONTH,
            ),
            go.Scatter(
                x=labels,
                y=view.monthly["moving_avg"],
                name="Média 3M",
                mode="lines",
                line={"color": AVERAGE, "width": 2.5, "dash": "dash"},
                hovertemplate="Média 3M<br>R$ %{y:,.2f}<extra></extra>",
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
            text=[f"R$ {v:,.0f}" for v in data[value_col]],
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
        return empty_figure("Nenhuma parcela futura", height=height)
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
        return empty_figure("Sem período anterior para comparar", height=height)
    data = by_cat.head(top_n).iloc[::-1]
    prev, cur = pop["previous_months"], pop["current_months"]
    fig = go.Figure(
        [
            go.Bar(
                y=data["category_label"],
                x=data["previous"],
                orientation="h",
                name=f"Anterior ({month_label(prev[0])}–{month_label(prev[-1])})",
                marker_color=PREVIOUS,
                hovertemplate="%{y}<br>R$ %{x:,.2f}<extra>Anterior</extra>",
            ),
            go.Bar(
                y=data["category_label"],
                x=data["current"],
                orientation="h",
                name=f"Atual ({month_label(cur[0])}–{month_label(cur[-1])})",
                marker_color=ACCENT,
                hovertemplate="%{y}<br>R$ %{x:,.2f}<extra>Atual</extra>",
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
        return empty_figure("Menos de dois anos de histórico", height=height)
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
        return empty_figure("Nenhuma parcela futura", height=height)
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
        annotation_text=f"Limite R$ {limit:,.0f}",
        annotation_position="top right",
        annotation_font={"color": LIMIT, "size": 11},
    )
    fig.update_layout(**plotly_layout(height=height))
    return fig
