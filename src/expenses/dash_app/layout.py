"""Static page structure. Everything data-dependent is filled by `callbacks.update_dashboard`."""

import pandas as pd
from dash import dcc, html

from src.expenses.config import format_currency_br
from src.expenses.dash_app.data import DEFAULT_PERIOD, PERIOD_LABELS
from src.expenses.dash_app.theme import category_color

GRAPH_CONFIG = {"displayModeBar": False}
FIGURE_IDS = ("monthly", "categories", "merchants", "commitments")
DROPDOWN_LABELS = {
    "select_all": "Selecionar todos",
    "deselect_all": "Limpar seleção",
    "selected_count": "{num_selected} selecionados",
    "search": "Buscar",
    "clear_search": "Limpar busca",
    "clear_selection": "Limpar",
    "no_options_found": "Nada encontrado",
}


def _card(title: str, *children) -> html.Div:
    return html.Div([html.H2(title, className="pe-section"), *children], className="pe-card")


def _graph(name: str) -> dcc.Graph:
    return dcc.Graph(id=f"fig-{name}", config=GRAPH_CONFIG)


def _filter(label: str, control, wide: bool = False) -> html.Div:
    return html.Div(
        [html.Label(label, htmlFor=control.id), control],
        className="pe-filter pe-filter-wide" if wide else "pe-filter",
    )


def kpi_card(card: dict) -> html.Div:
    return html.Div(
        [
            html.P(card["label"], className="pe-kpi-label"),
            html.P(card["value"], className="pe-kpi-value"),
            html.P(card["note"], className="pe-kpi-note"),
        ],
        className="pe-card pe-kpi",
        title=card["help"],
    )


def purchases_table(df: pd.DataFrame) -> html.Div:
    header = html.Thead(
        html.Tr(
            [
                html.Th("Data"),
                html.Th("Estabelecimento"),
                html.Th("Categoria", className="pe-col-category"),
                html.Th("Valor"),
            ]
        )
    )
    rows = [
        html.Tr(
            [
                html.Td(pd.Timestamp(row.date_buy).strftime("%d/%m/%Y")),
                html.Td(row.id),
                html.Td(
                    className="pe-col-category",
                    children=[
                        html.Span(
                            className="pe-dot",
                            style={"backgroundColor": category_color(row.category)},
                        ),
                        row.category_label,
                    ],
                ),
                html.Td(format_currency_br(row.cost), className="pe-num"),
            ]
        )
        for row in df.itertuples()
    ]
    return html.Div(
        html.Table([header, html.Tbody(rows)], className="pe-table"), className="pe-table-wrap"
    )


def build_layout(options: dict) -> html.Main:
    filters = html.Div(
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
                wide=True,
            ),
        ],
        className="pe-filters",
    )
    return html.Main(
        [
            html.Header(
                [
                    html.H1("Despesas", className="pe-title"),
                    html.P(id="subtitle", className="pe-subtitle"),
                ]
            ),
            filters,
            html.Section(id="kpis", className="pe-grid-4"),
            _card("Evolução mensal · média móvel 3 meses", _graph("monthly")),
            html.Section(
                [
                    _card("Por categoria", _graph("categories")),
                    _card("Top 10 estabelecimentos", _graph("merchants")),
                ],
                className="pe-grid-2",
            ),
            html.Section(
                [
                    _card("Parcelas futuras", _graph("commitments")),
                    _card("Maiores compras do período", html.Div(id="largest")),
                ],
                className="pe-grid-2",
            ),
        ],
        className="pe-page",
    )
