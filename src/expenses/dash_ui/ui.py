"""Mantine/AG Grid building blocks shared by every page (all labels in pt-BR)."""

import dash_ag_grid as dag
import dash_mantine_components as dmc
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

from src.expenses.dash_ui.insights_pt import Insight

SEVERITY_COLOR = {"info": "cyan", "good": "green", "warning": "yellow", "critical": "red"}
GRAPH_CONFIG = {"displaylogo": False, "displayModeBar": False}


def kpi(label: str, value: str, caption: str | None = None, delta: str | None = None, bad=None):
    """KPI tile. ``bad``: True colors the delta red, False green, None neutral."""
    color = {True: "red", False: "green", None: "dimmed"}[bad]
    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Text(label, size="xs", c="dimmed", tt="uppercase", fw=600),
                dmc.Text(value, size="xl", fw=700, className="money"),
                dmc.Text(delta, size="xs", c=color, fw=600, className="money") if delta else None,
                dmc.Text(caption, size="xs", c="dimmed", className="money") if caption else None,
            ],
            gap=2,
        ),
        withBorder=True,
        p="md",
        radius="md",
    )


def kpi_grid(*tiles, cols: int = 4) -> dmc.SimpleGrid:
    return dmc.SimpleGrid(
        list(tiles), cols={"base": 1, "xs": 2, "md": min(cols, 3), "lg": cols}, spacing="md"
    )


def insight_card(insight: Insight) -> dmc.Alert:
    return dmc.Alert(
        dcc.Markdown(insight.message, className="money insight-md"),
        title=f"{insight.icon} {insight.title}",
        color=SEVERITY_COLOR.get(insight.severity, "cyan"),
        variant="light",
        radius="md",
    )


def insight_stack(insights: list[Insight | None], cols: int = 1):
    cards = [insight_card(i) for i in insights if i is not None]
    if cols == 1:
        return dmc.Stack(cards, gap="sm")
    return dmc.SimpleGrid(cards, cols={"base": 1, "sm": 2, "lg": cols}, spacing="sm")


def panel(title: str | None, *children, subtitle: str | None = None, **props) -> dmc.Paper:
    head = []
    if title:
        head.append(dmc.Title(title, order=5))
    if subtitle:
        head.append(dmc.Text(subtitle, size="xs", c="dimmed"))
    return dmc.Paper(
        dmc.Stack([*head, *children], gap="sm"), withBorder=True, p="md", radius="md", **props
    )


def section(title: str, subtitle: str | None = None) -> dmc.Stack:
    return dmc.Stack(
        [
            dmc.Title(title, order=3),
            dmc.Text(subtitle, size="sm", c="dimmed") if subtitle else None,
        ],
        gap=2,
        mt="md",
    )


def two_col(left, right, ratio: str = "3fr 2fr") -> html.Div:
    """Responsive two-column row (stacks below 992px). ``ratio`` is the desktop split."""
    return html.Div([left, right], className="two-col", style={"--cols": ratio})


def empty(text: str = "Sem dados para os filtros selecionados.") -> dmc.Center:
    return dmc.Center(dmc.Text(text, c="dimmed", size="sm"), p="xl")


def empty_figure(text: str = "Sem dados") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=text, showarrow=False, font={"size": 14, "color": "#888"})
    fig.update_layout(
        height=280,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"visible": False},
        yaxis={"visible": False},
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
    )
    return fig


def fig_or_empty(fig: go.Figure | None) -> go.Figure:
    return fig if fig is not None else empty_figure()


def graph(fig: go.Figure | None = None, *, id: str | None = None, **props) -> dcc.Graph:
    kwargs = {"id": id} if id else {}
    return dcc.Graph(
        figure=fig_or_empty(fig), config=GRAPH_CONFIG, className="graph", **kwargs, **props
    )


def dynamic_graph(fig: go.Figure | None, message: str = "Sem dados para exibir.") -> html.Div:
    return graph(fig) if fig is not None else empty(message)


GRID_LOCALE = {
    "page": "Página",
    "more": "Mais",
    "to": "a",
    "of": "de",
    "next": "Próxima",
    "last": "Última",
    "first": "Primeira",
    "previous": "Anterior",
    "pageSizeSelectorLabel": "Linhas por página:",
    "noRowsToShow": "Sem linhas",
    "loadingOoo": "Carregando…",
}

# JS value formatters (AG Grid evaluates these expression strings; no custom JS file needed).
_BRL = "params.value == null ? '' : params.value.toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'})"
_NUM1 = "params.value == null ? '' : params.value.toLocaleString('pt-BR', {minimumFractionDigits: 1, maximumFractionDigits: 1})"
_INT = "params.value == null ? '' : params.value.toLocaleString('pt-BR')"


def data_table(
    df: pd.DataFrame,
    *,
    money: tuple[str, ...] = (),
    decimal: tuple[str, ...] = (),
    integer: tuple[str, ...] = (),
    page_size: int = 10,
    empty_text: str = "Nenhum registro.",
) -> html.Div | dmc.Center:
    """Sortable, filterable, paginated AG Grid. Dates are rendered as ``YYYY-MM-DD`` text."""
    if df.empty:
        return empty(empty_text)
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d")
    defs = []
    for col in df.columns:
        spec: dict = {"field": col, "headerName": col}
        if col in money:
            spec |= {"type": "rightAligned", "valueFormatter": {"function": _BRL}}
        elif col in decimal:
            spec |= {"type": "rightAligned", "valueFormatter": {"function": _NUM1}}
        elif col in integer:
            spec |= {"type": "rightAligned", "valueFormatter": {"function": _INT}}
        defs.append(spec)
    grid = dag.AgGrid(
        rowData=df.to_dict("records"),
        columnDefs=defs,
        defaultColDef={
            "sortable": True,
            "resizable": True,
            "suppressHeaderFilterButton": True,
            "suppressHeaderMenuButton": True,
            "flex": 1,
            "minWidth": 110,
        },
        dashGridOptions={
            "pagination": len(df) > page_size,
            "paginationPageSize": page_size,
            "domLayout": "autoHeight",
            "animateRows": False,
            "suppressCellFocus": True,
            "localeText": GRID_LOCALE,
        },
        style={"width": "100%"},
    )
    return html.Div(grid, className="money table-wrap")
