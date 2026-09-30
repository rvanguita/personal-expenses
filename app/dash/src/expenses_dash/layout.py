"""Page structure and shared components.

The header, filters and tab strip are static. The Overview tab has fixed component ids filled by
`callbacks.update_dashboard`; every other tab is a single container whose children come from
`pages.py`, rendered only while that tab is open.
"""

import pandas as pd
from dash import dcc, html

from expenses_dash.data import DEFAULT_PERIOD, PERIOD_LABELS, month_label
from expenses_dash.fmt import brl, integer, pct
from expenses_dash.theme import category_color

GRAPH_CONFIG = {"displayModeBar": False}
FIGURE_IDS = ("monthly", "categories", "merchants", "commitments")
TABS = (
    ("overview", "Visão geral"),
    ("trends", "Tendências"),
    ("habits", "Hábitos"),
    ("watchlist", "Atenção"),
    ("category", "Categorias"),
    ("reports", "Relatórios"),
)
DROPDOWN_LABELS = {
    "select_all": "Selecionar todos",
    "deselect_all": "Limpar seleção",
    "selected_count": "{num_selected} selecionados",
    "search": "Buscar",
    "clear_search": "Limpar busca",
    "clear_selection": "Limpar",
    "no_options_found": "Nada encontrado",
}


# --------------------------------------------------------------------------- components


def card(title: str, *children, note: str | None = None) -> html.Div:
    head = [html.H2(title, className="pe-section")]
    if note:
        head.append(html.P(note, className="pe-card-note"))
    return html.Div([*head, *children], className="pe-card")


def graph(figure, graph_id: str | None = None) -> dcc.Graph:
    props = {"config": GRAPH_CONFIG}
    if graph_id:
        props["id"] = graph_id
    if figure is not None:
        props["figure"] = figure
    return dcc.Graph(**props)


def kpi_card(card: dict) -> html.Div:
    return html.Div(
        [
            html.P(card["label"], className="pe-kpi-label"),
            html.P(card["value"], className="pe-kpi-value"),
            html.P(card["note"], className=f"pe-kpi-note pe-tone-{card.get('tone', 'neutral')}"),
        ],
        className="pe-card pe-kpi",
        title=card.get("help", ""),
    )


def kpi_row(cards: list[dict]) -> html.Section:
    return html.Section([kpi_card(c) for c in cards], className="pe-grid-4")


def row(*children) -> html.Section:
    return html.Section(list(children), className="pe-grid-2")


def empty(message: str) -> html.P:
    return html.P(message, className="pe-empty")


def _cell(value, kind: str, record) -> html.Td:
    if kind == "money":
        return html.Td(brl(value), className="pe-num")
    if kind == "date":
        return html.Td(pd.Timestamp(value).strftime("%d/%m/%Y") if pd.notna(value) else "—")
    if kind == "month":
        return html.Td(month_label(value))
    if kind == "pct":
        return html.Td(pct(value, signed=True), className="pe-num")
    if kind == "rate":
        return html.Td(f"{value:.1f}".replace(".", ","), className="pe-num")
    if kind == "int":
        return html.Td(integer(value), className="pe-num")
    if kind == "category":
        dot = html.Span(
            className="pe-dot", style={"backgroundColor": category_color(record["category"])}
        )
        return html.Td([dot, value], className="pe-col-category")
    return html.Td(value)


_NUMERIC = {"money", "pct", "rate", "int"}


def table(df: pd.DataFrame, columns: list[tuple[str, str, str]], max_rows: int | None = None):
    """``columns`` = [(header, column, kind)], kind in text/money/date/month/pct/rate/int/category
    (``category`` also needs a ``category`` key column for the colour dot)."""
    if df.empty:
        return empty("Nada para mostrar.")
    data = df.head(max_rows) if max_rows else df
    header = html.Thead(
        html.Tr(
            [
                html.Th(
                    title,
                    className=" ".join(
                        c
                        for c in (
                            "pe-num" if kind in _NUMERIC else "",
                            "pe-col-category" if kind == "category" else "",
                        )
                        if c
                    )
                    or None,
                )
                for title, _col, kind in columns
            ]
        )
    )
    body = html.Tbody(
        [
            html.Tr([_cell(record[col], kind, record) for _title, col, kind in columns])
            for record in data.to_dict("records")
        ]
    )
    return html.Div(html.Table([header, body], className="pe-table"), className="pe-table-wrap")


def purchases_table(df: pd.DataFrame) -> html.Div:
    return table(
        df,
        [
            ("Data", "date_buy", "date"),
            ("Estabelecimento", "id", "text"),
            ("Categoria", "category_label", "category"),
            ("Valor", "cost", "money"),
        ],
    )


# --------------------------------------------------------------------------- page


def _filter(label: str, control) -> html.Div:
    return html.Div([html.Label(label, htmlFor=control.id), control], className="pe-filter")


def _filters(options: dict) -> html.Div:
    return html.Div(
        [
            _filter(
                "Período",
                dcc.Dropdown(
                    id="f-period",
                    options=[{"label": v, "value": k} for k, v in PERIOD_LABELS.items()],
                    value=DEFAULT_PERIOD,
                    clearable=False,
                    searchable=False,
                    labels=DROPDOWN_LABELS,
                ),
            ),
            _filter(
                "Titular",
                dcc.Dropdown(
                    id="f-holders",
                    options=options["holders"],
                    multi=True,
                    placeholder="Todos",
                    labels=DROPDOWN_LABELS,
                ),
            ),
            _filter(
                "Categoria",
                dcc.Dropdown(
                    id="f-categories",
                    options=[{"label": lbl, "value": key} for key, lbl in options["categories"]],
                    multi=True,
                    placeholder="Todas",
                    labels=DROPDOWN_LABELS,
                ),
            ),
        ],
        className="pe-filters",
    )


def _overview() -> list:
    return [
        html.Section(id="kpis", className="pe-grid-4"),
        card("Evolução mensal · média móvel 3 meses", graph(None, "fig-monthly")),
        row(
            card("Por categoria", graph(None, "fig-categories")),
            card("Top 10 estabelecimentos", graph(None, "fig-merchants")),
        ),
        row(
            card("Parcelas futuras", graph(None, "fig-commitments")),
            card("Maiores compras do período", html.Div(id="largest")),
        ),
    ]


def _category_tab() -> list:
    picker = html.Div(
        _filter(
            "Categoria analisada",
            dcc.Dropdown(
                id="f-category-detail", clearable=False, searchable=True, labels=DROPDOWN_LABELS
            ),
        ),
        className="pe-picker",
    )
    return [picker, html.Div(id="category-content")]


def _reports_tab() -> list:
    return [
        html.Div(id="reports-content"),
        html.Div(
            [
                html.Button("Baixar CSV da seleção", id="btn-csv", className="pe-button"),
                dcc.Download(id="download-csv"),
            ],
            className="pe-actions",
        ),
    ]


def build_layout(options: dict) -> html.Main:
    bodies = {
        "overview": _overview(),
        "trends": [html.Div(id="trends-content")],
        "habits": [html.Div(id="habits-content")],
        "watchlist": [html.Div(id="watchlist-content")],
        "category": _category_tab(),
        "reports": _reports_tab(),
    }
    tabs = dcc.Tabs(
        id="tabs",
        value="overview",
        className="pe-tabs",
        parent_className="pe-tabs-parent",
        content_className="pe-tab-content",
        children=[
            dcc.Tab(
                label=label,
                value=value,
                className="pe-tab",
                selected_className="pe-tab--selected",
                children=bodies[value],
            )
            for value, label in TABS
        ],
    )
    return html.Main(
        [
            html.Header(
                [
                    html.H1("Despesas", className="pe-title"),
                    html.P(id="subtitle", className="pe-subtitle"),
                ]
            ),
            _filters(options),
            tabs,
        ],
        className="pe-page",
    )
