"""The single callback: controls -> subtitle, KPIs, largest-purchases table and four figures."""

from collections.abc import Callable

import pandas as pd
from dash import Dash, Input, Output, html

from src.expenses.dash_app.data import DEFAULT_PERIOD, build_view, kpi_cards
from src.expenses.dash_app.figures import (
    category_figure,
    commitments_figure,
    merchants_figure,
    monthly_figure,
)
from src.expenses.dash_app.layout import FIGURE_IDS, kpi_card, purchases_table


def update_dashboard(
    df_full: pd.DataFrame, period: str | None, holders: list | None, categories: list | None
) -> tuple:
    """Pure callback body: (subtitle, kpis, table, monthly, categories, merchants, commitments)."""
    view = build_view(df_full, period or DEFAULT_PERIOD, holders, categories)
    subtitle = view.period_label
    if view.last_invoice:
        subtitle += f" · última fatura em {view.last_invoice}"
    if view.is_empty:
        kpis = [html.P("Nenhuma transação para os filtros selecionados.", className="pe-empty")]
        table = []
    else:
        kpis = [kpi_card(card) for card in kpi_cards(view)]
        table = purchases_table(view.largest)
    figures = (
        monthly_figure(view),
        category_figure(view),
        merchants_figure(view),
        commitments_figure(view),
    )
    return (subtitle, kpis, table, *figures)


def register_callbacks(app: Dash, loader: Callable[[], pd.DataFrame]) -> None:
    @app.callback(
        Output("subtitle", "children"),
        Output("kpis", "children"),
        Output("largest", "children"),
        *(Output(f"fig-{name}", "figure") for name in FIGURE_IDS),
        Input("f-period", "value"),
        Input("f-holders", "value"),
        Input("f-categories", "value"),
    )
    def _update(period, holders, categories):
        return update_dashboard(loader(), period, holders, categories)
