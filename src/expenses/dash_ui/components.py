"""Small Dash building blocks (cards, KPI tiles, tables) shared by every tab."""

import pandas as pd
import plotly.graph_objects as go
from dash import dash_table, dcc, html
from dash.dash_table.Format import Format, Group, Scheme, Symbol

from src.expenses.ui.charts import STATUS_COLORS
from src.expenses.ui.insights import Insight

_SEVERITY_COLORS = {
    "info": "#00ACC1",
    "good": STATUS_COLORS["good"],
    "warning": STATUS_COLORS["warning"],
    "critical": STATUS_COLORS["critical"],
}

MONEY = Format(
    scheme=Scheme.fixed, precision=2, group=Group.yes, symbol=Symbol.yes, symbol_prefix="R$ "
)
PERCENT = Format(scheme=Scheme.fixed, precision=1)
INTEGER = Format(scheme=Scheme.fixed, precision=0, group=Group.yes)


def insight_card(insight: Insight) -> html.Div:
    return html.Div(
        [
            html.Div(f"{insight.icon} {insight.title}", className="insight-title"),
            dcc.Markdown(insight.message, className="insight-message"),
        ],
        className="insight-card",
        style={"borderLeftColor": _SEVERITY_COLORS.get(insight.severity, _SEVERITY_COLORS["info"])},
    )


def insight_cards(insights: list[Insight | None]) -> list[html.Div]:
    return [insight_card(i) for i in insights if i is not None]


def kpi(
    label: str, value: str, caption: str | None = None, delta: str | None = None, *, delta_bad=None
):
    """KPI tile. ``delta_bad`` colors the delta red (True), green (False) or muted (None)."""
    children = [
        html.Div(label, className="kpi-label"),
        html.Div(value, className="kpi-value money"),
    ]
    if delta:
        kind = {True: "bad", False: "good", None: "flat"}[delta_bad]
        children.append(html.Div(delta, className=f"kpi-delta money {kind}"))
    if caption:
        children.append(html.Div(caption, className="kpi-caption money"))
    return html.Div(children, className="kpi")


def kpi_row(*tiles) -> html.Div:
    return html.Div(list(tiles), className="kpi-row")


def card(title: str | None, *children, className: str = "") -> html.Div:
    header = [html.H4(title, className="card-title")] if title else []
    return html.Div([*header, *children], className=f"card {className}".strip())


def grid(*cells, columns: str = "1fr 1fr") -> html.Div:
    return html.Div(list(cells), className="grid", style={"gridTemplateColumns": columns})


def graph(fig: go.Figure | None, empty: str = "No data to plot.") -> html.Div | dcc.Graph:
    if fig is None:
        return note(empty)
    return dcc.Graph(figure=fig, config={"displaylogo": False}, className="graph")


def note(text: str) -> html.Div:
    return html.Div(text, className="note")


def section(title: str, caption: str | None = None) -> html.Div:
    return html.Div(
        [html.H3(title, className="section-title")]
        + ([html.P(caption, className="section-caption")] if caption else [])
    )


def table(
    df: pd.DataFrame,
    *,
    money: tuple[str, ...] = (),
    percent: tuple[str, ...] = (),
    integer: tuple[str, ...] = (),
    page_size: int = 15,
    empty: str = "No rows.",
) -> html.Div:
    """Sortable, paginated table. Dates are rendered as ``YYYY-MM-DD`` strings."""
    if df.empty:
        return note(empty)
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d")
    columns = []
    for col in df.columns:
        spec = {"name": col, "id": col}
        if col in money:
            spec |= {"type": "numeric", "format": MONEY}
        elif col in percent:
            spec |= {"type": "numeric", "format": PERCENT}
        elif col in integer:
            spec |= {"type": "numeric", "format": INTEGER}
        columns.append(spec)
    data_table = dash_table.DataTable(
        data=df.to_dict("records"),
        columns=columns,
        sort_action="native",
        page_size=page_size,
        style_as_list_view=True,
        style_cell_conditional=[
            {"if": {"column_id": c}, "textAlign": "right"} for c in (*money, *percent, *integer)
        ],
        css=[{"selector": ".dash-spreadsheet", "rule": "font-family: inherit;"}],
    )
    return html.Div(data_table, className="expenses-table")
