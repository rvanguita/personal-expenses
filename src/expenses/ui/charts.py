import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.expenses.config import format_currency_br

# Dark defaults kept as module constants for callers that import them; the helpers below pick the
# light or dark value from the active Streamlit theme base at figure-build time.
GRID_COLOR = "#334155"
AXIS_TEXT_COLOR = "#F8FAFC"

_GRID_COLOR_LIGHT = "#D0D7DE"
_AXIS_TEXT_LIGHT = "#1F2933"
_TOTAL_LINE_DARK = "#FFFFFF"
_TOTAL_LINE_LIGHT = "#1F2933"


def _is_light_theme() -> bool:
    try:
        return st.get_option("theme.base") == "light"
    except Exception:  # noqa: BLE001
        return False


def grid_color() -> str:
    return _GRID_COLOR_LIGHT if _is_light_theme() else GRID_COLOR


def axis_text_color() -> str:
    return _AXIS_TEXT_LIGHT if _is_light_theme() else AXIS_TEXT_COLOR


def total_line_color() -> str:
    return _TOTAL_LINE_LIGHT if _is_light_theme() else _TOTAL_LINE_DARK


def amounts_hidden() -> bool:
    """True when the sidebar 'Hide amounts' toggle is on, so chart builders drop on-plot currency
    text labels (which a full-chart CSS blur doesn't fully obscure)."""
    try:
        return bool(st.session_state.get("hide_amounts", False))
    except Exception:  # noqa: BLE001
        return False


# Fixed, reserved status palette — only used when a color means good/bad, never for a plain series.
STATUS_COLORS = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
}

# "Current vs previous" / "highlighted vs context" emphasis pair, formalizing the accent/muted
# convention already used ad hoc across the dashboard.
EMPHASIS_ACCENT = "#00ACC1"
EMPHASIS_MUTED = "#607D8B"

_LEGEND_TOP = {
    "orientation": "h",
    "yanchor": "bottom",
    "y": 1.02,
    "xanchor": "left",
    "x": 0.0,
    "font": {"size": 11},
}
_LEGEND_BOTTOM = {
    "orientation": "h",
    "yanchor": "bottom",
    "y": -0.32,
    "xanchor": "center",
    "x": 0.5,
    "font": {"size": 11},
}


def apply_chart_theme(fig: go.Figure, *, height: int = 380, legend: str = "top") -> go.Figure:
    """Applies the app's shared margin/grid/legend/font styling to a Plotly figure."""
    grid = grid_color()
    axis_text = axis_text_color()
    layout: dict = {
        "height": height,
        "margin": {"l": 10, "r": 15, "t": 30, "b": 45},
        # Transparent so the figure inherits the themed Streamlit container background (light or
        # dark); font/grid/tick colors follow the active theme base.
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": axis_text},
        "xaxis": {
            "gridcolor": grid,
            "tickfont": {"color": axis_text},
            "automargin": True,
        },
        "yaxis": {
            "gridcolor": grid,
            "tickfont": {"color": axis_text},
            "automargin": True,
        },
    }
    if legend == "top":
        layout["legend"] = _LEGEND_TOP
    elif legend == "bottom":
        layout["legend"] = _LEGEND_BOTTOM
    elif legend == "hidden":
        layout["showlegend"] = False
    fig.update_layout(**layout)
    return fig


def add_total_line_trace(
    fig: go.Figure,
    x,
    y,
    *,
    name: str = "Total",
    color: str | None = None,
    dash: str = "dash",
    point_labels: bool = False,
) -> go.Figure:
    """Overlays a total/reference line. With ``point_labels`` the R$ value is printed above every
    point; otherwise there are no on-plot labels and values are shown on hover."""
    if color is None:
        color = total_line_color()
    y_list = list(y)

    fig.add_trace(
        go.Scatter(
            x=list(x),
            y=y_list,
            mode="lines+markers+text" if point_labels else "lines+markers",
            name=name,
            line={"color": color, "width": 2.5, "dash": dash},
            marker={"size": 6, "color": color},
            text=[format_currency_br(v) for v in y_list] if point_labels else None,
            textposition="top center",
            textfont={"size": 11, "color": color},
            hovertemplate="R$ %{y:,.2f}<extra>%{fullData.name}</extra>",
            cliponaxis=False,
        )
    )
    return fig


def build_emphasis_bar_colors(labels: list[str], highlight_label: str | None) -> list[str]:
    """Flat color list: accent for the highlighted label (e.g. the peak day), muted gray for the rest."""
    return [EMPHASIS_ACCENT if lbl == highlight_label else EMPHASIS_MUTED for lbl in labels]


def build_ranked_bar_chart(
    df: pd.DataFrame,
    label_col: str,
    value_col: str,
    *,
    color: str = EMPHASIS_ACCENT,
    color_map: dict | None = None,
    height: int = 380,
) -> go.Figure:
    """Horizontal bar chart ranked by value (largest on top), with a value label outside each bar.

    Use `color_map` (e.g. CATEGORY_COLOR_MAP) when bars carry categorical identity; otherwise every
    bar takes the same flat `color` — never a continuous scale keyed to the bar's own value, which
    would double-encode magnitude that bar length already shows.
    """
    df_sorted = df.sort_values(by=value_col, ascending=True)
    bar_colors = (
        [color_map.get(lbl, EMPHASIS_ACCENT) for lbl in df_sorted[label_col]]
        if color_map is not None
        else color
    )

    fig = px.bar(
        df_sorted,
        x=value_col,
        y=label_col,
        orientation="h",
        text=None if amounts_hidden() else [format_currency_br(v) for v in df_sorted[value_col]],
    )
    fig.update_traces(
        marker_color=bar_colors,
        textposition="outside",
        cliponaxis=False,
        textfont={"size": 11},
    )
    max_val = float(df_sorted[value_col].max()) if not df_sorted.empty else 100.0
    axis_text = axis_text_color()
    fig.update_layout(
        height=height,
        margin={"l": 10, "r": 40, "t": 10, "b": 10},
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": axis_text},
        xaxis={
            "range": [0, max_val * 1.25],
            "title": "",
            "automargin": True,
            "gridcolor": grid_color(),
            "tickfont": {"color": axis_text},
        },
        yaxis={"title": "", "automargin": True, "tickfont": {"color": axis_text}},
    )
    return fig


def budget_status_color(is_over_limit: bool) -> str:
    """Fixed status color for an over-limit (critical) vs within-limit (good) budget signal."""
    return STATUS_COLORS["critical"] if is_over_limit else STATUS_COLORS["good"]
