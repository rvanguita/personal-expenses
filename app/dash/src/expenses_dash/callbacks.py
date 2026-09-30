"""Callbacks. Each tab renders only while it is open; the pure bodies are importable for tests."""

from collections.abc import Callable

import pandas as pd
from dash import Dash, Input, Output, State, dcc, html, no_update

from expenses_dash.analyses import (
    category_view,
    export_frame,
    habits_view,
    reports_view,
    trends_view,
    watchlist_view,
)
from expenses_dash.data import DEFAULT_PERIOD, build_view, kpi_cards
from expenses_dash.figures import (
    category_figure,
    commitments_figure,
    merchants_figure,
    monthly_figure,
)
from expenses_dash.layout import FIGURE_IDS, kpi_card, purchases_table
from expenses_dash.pages import (
    category_page,
    habits_page,
    reports_page,
    trends_page,
    watchlist_page,
)

FILTERS = (Input("f-period", "value"), Input("f-holders", "value"), Input("f-categories", "value"))


def update_dashboard(
    df_full: pd.DataFrame, period: str | None, holders: list | None, categories: list | None
) -> tuple:
    """Overview body: (subtitle, kpis, table, monthly, categories, merchants, commitments)."""
    view = build_view(df_full, period or DEFAULT_PERIOD, holders, categories)
    subtitle = view.period_label
    if view.last_invoice:
        subtitle += f" · latest invoice on {view.last_invoice}"
    if view.is_empty:
        kpis = [html.P("No transactions for the selected filters.", className="pe-empty")]
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


def render_tab(tab: str, df_full: pd.DataFrame, period, holders, categories) -> list:
    """Body of a secondary tab (``trends`` / ``habits`` / ``watchlist`` / ``reports``)."""
    if tab == "trends":
        return trends_page(trends_view(df_full, period, holders, categories))
    if tab == "habits":
        return habits_page(habits_view(df_full, period, holders, categories))
    if tab == "watchlist":
        return watchlist_page(watchlist_view(df_full, period, holders, categories))
    if tab == "reports":
        return reports_page(reports_view(df_full, period, holders, categories))
    raise ValueError(tab)


def render_category(df_full: pd.DataFrame, period, holders, categories, selected) -> tuple:
    """(page body, dropdown options, dropdown value) for the Categories tab."""
    view = category_view(df_full, period, holders, categories, selected)
    options = [{"label": label, "value": key} for key, label in view["options"]]
    return category_page(view), options, view["selected"]


def register_callbacks(app: Dash, loader: Callable[[], pd.DataFrame]) -> None:
    @app.callback(
        Output("subtitle", "children"),
        Output("kpis", "children"),
        Output("largest", "children"),
        *(Output(f"fig-{name}", "figure") for name in FIGURE_IDS),
        *FILTERS,
    )
    def _overview(period, holders, categories):
        return update_dashboard(loader(), period, holders, categories)

    for tab in ("trends", "habits", "watchlist", "reports"):

        @app.callback(Output(f"{tab}-content", "children"), Input("tabs", "value"), *FILTERS)
        def _secondary(active, period, holders, categories, _tab=tab):
            if active != _tab:
                return no_update
            return render_tab(_tab, loader(), period, holders, categories)

    @app.callback(
        Output("category-content", "children"),
        Output("f-category-detail", "options"),
        Output("f-category-detail", "value"),
        Input("tabs", "value"),
        *FILTERS,
        Input("f-category-detail", "value"),
    )
    def _category(active, period, holders, categories, selected):
        if active != "category":
            return no_update, no_update, no_update
        return render_category(loader(), period, holders, categories, selected)

    @app.callback(
        Output("download-csv", "data"),
        Input("btn-csv", "n_clicks"),
        State("f-period", "value"),
        State("f-holders", "value"),
        State("f-categories", "value"),
        prevent_initial_call=True,
    )
    def _download(_clicks, period, holders, categories):
        frame = export_frame(loader(), period, holders, categories)
        if frame.empty:
            return no_update
        return dcc.send_data_frame(
            frame.to_csv, "expenses.csv", index=False, sep=";", encoding="utf-8-sig"
        )
