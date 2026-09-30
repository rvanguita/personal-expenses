"""Dash frontend: the same single read-only dashboard as the Streamlit app, on port DASH_PORT.

Run with ``uv run python dash_app.py``. Data operations (ingest / categorize / manage) live only
in the Streamlit app.
"""

from collections.abc import Callable

import pandas as pd
from dash import Dash, Input, Output, dcc, html

from src.expenses.config import DASH_PORT, format_currency_br
from src.expenses.dashboard import (
    DEFAULT_PERIOD,
    PERIOD_LABELS,
    all_figures,
    build_view,
    filter_options,
    kpi_cards,
)

GRAPH_CONFIG = {"displayModeBar": False}
FIGURE_IDS = ("monthly", "categories", "merchants", "commitments")


def _card(title: str, *children, class_name: str = "") -> html.Div:
    return html.Div(
        [html.P(title, className="pe-section"), *children], className=f"pe-card {class_name}"
    )


def _kpi(card: dict) -> html.Div:
    return html.Div(
        [
            html.P(card["label"], className="pe-kpi-label"),
            html.P(card["value"], className="pe-kpi-value"),
            html.P(card["note"], className="pe-kpi-note"),
        ],
        className="pe-card pe-kpi",
        title=card["help"],
    )


def _table(df: pd.DataFrame) -> html.Div:
    head = html.Thead(
        html.Tr([html.Th(h) for h in ("Data", "Estabelecimento", "Categoria", "Valor")])
    )
    body = html.Tbody(
        [
            html.Tr(
                [
                    html.Td(pd.Timestamp(row.date_buy).strftime("%d/%m/%Y")),
                    html.Td(row.id),
                    html.Td(row.category_label),
                    html.Td(format_currency_br(row.cost), className="pe-num"),
                ]
            )
            for row in df.itertuples()
        ]
    )
    return html.Div(html.Table([head, body], className="pe-table"), className="pe-table-wrap")


def _graph(graph_id: str) -> dcc.Graph:
    return dcc.Graph(id=f"fig-{graph_id}", config=GRAPH_CONFIG)


def update_dashboard(
    df_full: pd.DataFrame, period: str, holders: list | None, categories: list | None
) -> tuple:
    """Pure callback body: (subtitle, kpi children, table children, *figures)."""
    view = build_view(df_full, period or DEFAULT_PERIOD, holders, categories)
    subtitle = view.period_label
    if view.last_invoice:
        subtitle += f" · última fatura em {view.last_invoice}"
    if view.is_empty:
        empty = html.P("Nenhuma transação para os filtros selecionados.", className="pe-empty")
        kpis, table = [empty], []
    else:
        kpis, table = [_kpi(card) for card in kpi_cards(view)], _table(view.largest)
    figures = all_figures(view)
    return (subtitle, kpis, table, *(figures[k] for k in FIGURE_IDS))


def create_app(loader: Callable[[], pd.DataFrame] | None = None) -> Dash:
    if loader is None:
        from src.expenses.database import load_expenses_data as loader

    options = filter_options(loader())
    app = Dash(__name__, title="Despesas", assets_folder="assets")

    filters = html.Div(
        [
            html.Div(
                [
                    html.Label("Período"),
                    dcc.Dropdown(
                        id="f-period",
                        options=[{"label": v, "value": k} for k, v in PERIOD_LABELS.items()],
                        value=DEFAULT_PERIOD,
                        clearable=False,
                    ),
                ]
            ),
            html.Div(
                [
                    html.Label("Titular"),
                    dcc.Dropdown(
                        id="f-holders",
                        options=options["holders"],
                        multi=True,
                        placeholder="Todos",
                    ),
                ]
            ),
            html.Div(
                [
                    html.Label("Categoria"),
                    dcc.Dropdown(
                        id="f-categories",
                        options=[{"label": lbl, "value": k} for k, lbl in options["categories"]],
                        multi=True,
                        placeholder="Todas",
                    ),
                ],
                className="pe-filter-wide",
            ),
        ],
        className="pe-filters",
    )

    app.layout = html.Main(
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

    @app.callback(
        Output("subtitle", "children"),
        Output("kpis", "children"),
        Output("largest", "children"),
        *(Output(f"fig-{k}", "figure") for k in FIGURE_IDS),
        Input("f-period", "value"),
        Input("f-holders", "value"),
        Input("f-categories", "value"),
    )
    def _update(period, holders, categories):
        return update_dashboard(loader(), period, holders, categories)

    return app


def main() -> None:
    create_app().run(host="0.0.0.0", port=DASH_PORT, debug=False)


if __name__ == "__main__":
    main()
