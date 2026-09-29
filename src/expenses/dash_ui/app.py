"""Dash frontend (Mantine, multi-page, cross-filter, pt-BR) over the shared Silver backend.

Pages (``dash_ui/pages``) only call ``data.get_frames`` (-> ``database.load_expenses_data`` +
``filters.apply_filters``), ``analytics`` and the shared ``ui.figures`` builders. Theme,
hide-amounts and language reach the Plotly figures through ``charts.chart_context``.
"""

import logging
from collections.abc import Callable
from pathlib import Path

import dash
import dash_mantine_components as dmc
import pandas as pd
from dash import Dash, Input, Output, State, callback_context, dcc, html, no_update
from dash.exceptions import PreventUpdate

from src.expenses.config import CATEGORY_CONFIG, LABEL_TO_CAT
from src.expenses.dash_ui import data
from src.expenses.dash_ui.shell import CROSS_FILTER_PATHS, MULTI_FILTERS, create_layout
from src.expenses.database import get_db_engine, load_expenses_data
from src.expenses.filters import DEFAULT_FILTERS, resolve_default_months
from src.expenses.runtime import clear_caches

logger = logging.getLogger("expenses.dash")

_HERE = Path(__file__).parent


def _checkboxes(values_labels: list[tuple[str, str]]) -> list:
    return [dmc.Checkbox(label=label, value=value, size="sm") for value, label in values_labels]


def _register_callbacks(app: Dash) -> None:
    # ------------------------------------------------------------ filter options / meta
    @app.callback(
        Output("meta", "data"),
        Output("banner", "children"),
        Input("refresh", "n_clicks"),
    )
    def load_meta(_refresh):
        if callback_context.triggered_id == "refresh":
            clear_caches()
        alerts = []
        if get_db_engine() is None:
            alerts.append(
                dmc.Alert(
                    "Configuração do banco não encontrada no `.env` "
                    "(MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST).",
                    title="⚠️ Banco de dados",
                    color="red",
                )
            )
        df = data.load_full()
        if df.empty:
            alerts.append(
                dmc.Alert(
                    "Nenhum dado encontrado. Carregue sua primeira fatura pelo app Streamlit "
                    "(aba Ingest Invoices).",
                    title="Sem dados",
                    color="yellow",
                )
            )
            return {"months": [], "holders": [], "cats": [], "total": 0}, alerts
        cats = [c for c in sorted(df["category"].unique()) if c in CATEGORY_CONFIG]
        meta = {
            "months": sorted(df["year_month"].unique().tolist(), reverse=True),
            "holders": sorted(h for h in df["source_debt"].unique() if h),
            "cats": cats,
            "total": len(df),
        }
        return meta, alerts

    @app.callback(
        Output("months-opts", "children"),
        Output("holders-opts", "children"),
        Output("cats-opts", "children"),
        Output("record-count", "children"),
        Input("meta", "data"),
    )
    def render_options(meta):
        if not meta:
            raise PreventUpdate
        return (
            _checkboxes([(m, m) for m in meta["months"]]),
            _checkboxes([(h, h) for h in meta["holders"]]),
            _checkboxes([(c, CATEGORY_CONFIG[c]["label"]) for c in meta["cats"]]),
            f"{meta['total']:,} transações".replace(",", "."),
        )

    for key in ("holders", "cats"):

        @app.callback(
            Output(f"{key}-value", "value"),
            Input("meta", "data"),
            Input(f"{key}-all", "n_clicks"),
            Input(f"{key}-none", "n_clicks"),
            prevent_initial_call=True,
        )
        def set_multi(meta, _all, _none, key=key):
            if not meta:
                raise PreventUpdate
            if callback_context.triggered_id == f"{key}-none":
                return []
            return meta[key]

    @app.callback(
        Output("months-value", "value"),
        Input("period", "value"),
        Input("meta", "data"),
        Input("months-all", "n_clicks"),
        Input("months-none", "n_clicks"),
    )
    def set_months(period, meta, _all, _none):
        if not meta:
            raise PreventUpdate
        trigger = callback_context.triggered_id
        if trigger == "months-all":
            return meta["months"]
        if trigger == "months-none":
            return []
        return resolve_default_months(period, meta["months"])

    for key, label in MULTI_FILTERS.items():

        @app.callback(
            Output(f"{key}-btn", "children"),
            Input(f"{key}-value", "value"),
            Input("meta", "data"),
        )
        def button_label(selected, meta, key=key, label=label):
            if not meta:
                return label
            return f"{label} ({len(selected or [])}/{len(meta[key])})"

    @app.callback(
        Output("filters", "data"),
        Input("months-value", "value"),
        Input("holders-value", "value"),
        Input("cats-value", "value"),
        Input("tx-type", "value"),
        Input("installment-type", "value"),
        Input("search-id", "value"),
        State("meta", "data"),
    )
    def collect_filters(months, holders, cats, tx_type, installment_type, search, meta):
        if not meta:
            raise PreventUpdate
        return {
            **DEFAULT_FILTERS,
            "selected_months": months or [],
            "selected_holders": holders or [],
            "selected_categories": cats or [],
            "tx_type": tx_type,
            "installment_type": installment_type,
            "search_id": search or "",
        }

    # ------------------------------------------------------------ theme / privacy
    @app.callback(
        Output("theme", "data"),
        Input("theme-toggle", "n_clicks"),
        State("theme", "data"),
        prevent_initial_call=True,
    )
    def toggle_theme(_clicks, current):
        return "light" if current == "dark" else "dark"

    app.clientside_callback(
        """
        function(theme, hide) {
            document.body.dataset.agThemeMode = theme;
            document.documentElement.classList.toggle('hide-amounts', !!hide);
            return theme;
        }
        """,
        Output("mantine", "forceColorScheme"),
        Input("theme", "data"),
        Input("hide-switch", "checked"),
    )

    # ------------------------------------------------------------ cross-filter chips
    @app.callback(
        Output("selection-chips", "children"),
        Input("selection", "data"),
        Input("url", "pathname"),
    )
    def show_selection(selection, pathname):
        selection = selection or {}
        if pathname not in CROSS_FILTER_PATHS or not (
            selection.get("month") or selection.get("category")
        ):
            return None
        badges = []
        if selection.get("month"):
            badges.append(dmc.Badge(f"Fatura: {selection['month']}", size="lg", variant="light"))
        if selection.get("category"):
            label = CATEGORY_CONFIG.get(selection["category"], {}).get(
                "label", selection["category"]
            )
            badges.append(
                dmc.Badge(f"Categoria: {label}", size="lg", variant="light", color="grape")
            )
        return dmc.Group(
            [
                dmc.Text("Filtro por clique:", size="sm", c="dimmed"),
                *badges,
                dmc.Button("✕ Limpar", id="clear-selection", size="compact-sm", variant="subtle"),
            ],
            gap="xs",
        )

    @app.callback(
        Output("selection", "data", allow_duplicate=True),
        Input("clear-selection", "n_clicks"),
        prevent_initial_call=True,
    )
    def clear_selection(clicks):
        if not clicks:
            raise PreventUpdate
        return {}


def create_app(data_loader: Callable[[], pd.DataFrame] = load_expenses_data) -> Dash:
    """Builds the Dash app. ``data_loader`` returns the Silver frame (injectable for tests)."""
    data.configure(data_loader)
    app = Dash(
        __name__,
        use_pages=True,
        pages_folder=str(_HERE / "pages"),
        assets_folder=str(_HERE / "assets"),
        external_stylesheets=dmc.styles.ALL,
        suppress_callback_exceptions=True,
        title="Despesas & Inteligência Financeira",
    )
    app.layout = create_layout
    _register_callbacks(app)
    return app


__all__ = ["LABEL_TO_CAT", "create_app", "dash", "dcc", "html", "no_update"]
