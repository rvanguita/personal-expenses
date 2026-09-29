"""Dash frontend: same Silver data, filters, analytics and figures as the Streamlit app.

``create_app`` wires a static layout (sidebar filters + four analytic tabs) to callbacks that
only call the shared backend (``database.load_expenses_data``, ``filters.apply_filters``,
``analytics`` via the ``dash_ui.tabs`` view builders and ``ui.figures``).
"""

import logging
from collections.abc import Callable
from pathlib import Path

import pandas as pd
from dash import Dash, Input, Output, State, callback_context, dcc, html, no_update
from dash.exceptions import PreventUpdate

from src.expenses.config import CATEGORY_CONFIG
from src.expenses.dash_ui.components import note
from src.expenses.dash_ui.tabs import (
    DEFAULT_REF_LIMIT,
    build_category_view,
    build_dashboard_view,
    build_reports_view,
    build_trends_view,
    category_options,
    export_csv,
)
from src.expenses.database import get_db_engine, load_expenses_data
from src.expenses.filters import (
    DEFAULT_FILTERS,
    INSTALLMENT_OPTIONS,
    PERIOD_OPTIONS,
    TX_NET,
    TX_TYPE_OPTIONS,
    apply_filters,
    resolve_default_months,
)
from src.expenses.runtime import clear_caches
from src.expenses.ui.charts import chart_context
from src.expenses.ui.figures import CHART_STYLE_LINES, CHART_STYLE_STACKED

logger = logging.getLogger("expenses.dash")

TABS = [
    ("dashboard", "📊 General Dashboard"),
    ("trends", "📈 Trends & Insights"),
    ("category", "🔍 Category Analysis"),
    ("reports", "📑 Reports & Projections"),
]
_SOURCE_INVOICE, _SOURCE_PURCHASE = "year_month", "buy_year_month"


def _options(values: list[str]) -> list[dict]:
    return [{"label": v, "value": v} for v in values]


def _field(label: str, control) -> html.Div:
    return html.Div([html.Label(label, className="field-label"), control], className="field")


def _sidebar() -> html.Aside:
    return html.Aside(
        [
            html.H3("⚙️ Dashboard Filters"),
            html.Button("☀️ / 🌙 Toggle theme", id="theme-toggle", className="btn"),
            dcc.Checklist(
                id="hide-toggle",
                options=[{"label": " 🙈 Hide amounts", "value": "hide"}],
                value=[],
                persistence=True,
                persistence_type="local",
                className="check",
            ),
            html.Hr(),
            _field(
                "📅 Predefined Period",
                dcc.Dropdown(
                    id="period",
                    options=_options(PERIOD_OPTIONS),
                    value=PERIOD_OPTIONS[0],
                    clearable=False,
                ),
            ),
            _field(
                "Selected Invoices (Year-Month)",
                dcc.Dropdown(id="months", options=[], value=[], multi=True),
            ),
            _field(
                "👤 Cardholder (Portador)",
                dcc.Dropdown(id="holders", options=[], value=[], multi=True),
            ),
            html.Div(
                [
                    html.Button("Select All", id="cats-all", className="btn small"),
                    html.Button("Deselect All", id="cats-none", className="btn small"),
                ],
                className="btn-row",
            ),
            _field("🏷️ Categories", dcc.Dropdown(id="categories", options=[], value=[], multi=True)),
            _field(
                "Transaction Type",
                dcc.RadioItems(
                    id="tx-type", options=_options(TX_TYPE_OPTIONS), value=TX_NET, className="radio"
                ),
            ),
            _field(
                "Payment Method",
                dcc.Dropdown(
                    id="installment-type",
                    options=_options(INSTALLMENT_OPTIONS),
                    value=INSTALLMENT_OPTIONS[0],
                    clearable=False,
                ),
            ),
            _field(
                "🔍 Search Merchant",
                dcc.Input(
                    id="search-id",
                    type="text",
                    debounce=True,
                    placeholder="E.g.: Example Market...",
                    className="text-input",
                ),
            ),
            html.Hr(),
            html.Button("🔄 Refresh / Clear Cache", id="refresh", n_clicks=0, className="btn"),
            html.Div(id="record-count", className="caption"),
        ],
        className="sidebar",
    )


def _tab_panel(key: str, *children) -> html.Div:
    return html.Div(
        [*children, dcc.Loading(html.Div(id=f"content-{key}"), type="dot")],
        id=f"panel-{key}",
        className="panel",
    )


def create_layout() -> html.Div:
    return html.Div(
        [
            dcc.Store(id="filters"),
            dcc.Store(id="theme", storage_type="local", data="dark"),
            dcc.Download(id="download-csv"),
            html.Header(
                [
                    html.H1("💳 Expenses & Financial Intelligence"),
                    html.P(
                        "Credit card expenses analytics dashboard with AI-powered categorization"
                    ),
                ],
                className="header",
            ),
            html.Div(
                [
                    _sidebar(),
                    html.Main(
                        [
                            html.Div(id="banner"),
                            dcc.Tabs(
                                id="tabs",
                                value=TABS[0][0],
                                children=[dcc.Tab(label=label, value=key) for key, label in TABS],
                                className="tabs",
                            ),
                            _tab_panel(
                                "dashboard",
                                html.Div(
                                    [
                                        _field(
                                            "Group timeline by",
                                            dcc.RadioItems(
                                                id="timeline",
                                                options=[
                                                    {
                                                        "label": " 📅 Invoice date",
                                                        "value": _SOURCE_INVOICE,
                                                    },
                                                    {
                                                        "label": " 🛒 Purchase date",
                                                        "value": _SOURCE_PURCHASE,
                                                    },
                                                ],
                                                value=_SOURCE_INVOICE,
                                                inline=True,
                                                className="radio",
                                            ),
                                        ),
                                        _field(
                                            "Chart view",
                                            dcc.RadioItems(
                                                id="chart-style",
                                                options=[
                                                    {
                                                        "label": " 📊 Stacked",
                                                        "value": CHART_STYLE_STACKED,
                                                    },
                                                    {
                                                        "label": " 📈 Trend lines",
                                                        "value": CHART_STYLE_LINES,
                                                    },
                                                ],
                                                value=CHART_STYLE_STACKED,
                                                inline=True,
                                                className="radio",
                                            ),
                                        ),
                                    ],
                                    className="toolbar",
                                ),
                            ),
                            _tab_panel("trends"),
                            _tab_panel(
                                "category",
                                html.Div(
                                    _field(
                                        "Select a category to analyze in detail",
                                        dcc.Dropdown(
                                            id="category-detail", options=[], clearable=False
                                        ),
                                    ),
                                    className="toolbar",
                                ),
                            ),
                            _tab_panel(
                                "reports",
                                html.Div(
                                    [
                                        _field(
                                            "🎯 Reference Budget Limit (R$)",
                                            dcc.Input(
                                                id="ref-limit",
                                                type="number",
                                                value=DEFAULT_REF_LIMIT,
                                                min=100,
                                                step=500,
                                                debounce=True,
                                                className="text-input",
                                            ),
                                        ),
                                        html.Button(
                                            "📥 Download Report as CSV",
                                            id="download-btn",
                                            className="btn",
                                        ),
                                    ],
                                    className="toolbar",
                                ),
                            ),
                        ],
                        className="main",
                    ),
                ],
                className="shell",
            ),
        ],
        id="app-root",
    )


def create_app(data_loader: Callable[[], pd.DataFrame] = load_expenses_data) -> Dash:
    """Builds the Dash app. ``data_loader`` returns the Silver frame (injectable for tests)."""
    app = Dash(
        __name__,
        title="Expenses & Financial Intelligence",
        assets_folder=str(Path(__file__).parent / "assets"),
        suppress_callback_exceptions=False,
    )
    app.layout = create_layout

    # ------------------------------------------------------------------ sidebar / filters
    @app.callback(
        Output("months", "options"),
        Output("holders", "options"),
        Output("holders", "value"),
        Output("categories", "options"),
        Output("categories", "value"),
        Output("record-count", "children"),
        Output("banner", "children"),
        Input("refresh", "n_clicks"),
        Input("cats-all", "n_clicks"),
        Input("cats-none", "n_clicks"),
        State("categories", "options"),
    )
    def load_filter_options(_refresh, _all, _none, current_cat_options):
        trigger = callback_context.triggered_id
        if trigger == "cats-all":
            return (
                *[no_update] * 4,
                [o["value"] for o in current_cat_options],
                no_update,
                no_update,
            )
        if trigger == "cats-none":
            return (*[no_update] * 4, [], no_update, no_update)
        if trigger == "refresh":
            clear_caches()

        banner = None
        if get_db_engine() is None:
            banner = html.Div(
                "⚠️ Database configuration not found in `.env`. Check MYSQL_USER, MYSQL_PASSWORD, "
                "MYSQL_HOST.",
                className="alert critical",
            )
        df_full = data_loader()
        if df_full.empty:
            return (
                [],
                [],
                [],
                [],
                [],
                "No data found in the database.",
                banner
                or note(
                    "No data found. Use the Streamlit app's Ingest Invoices tab to load your first invoice."
                ),
            )

        months = sorted(df_full["year_month"].unique().tolist(), reverse=True)
        holders = sorted(h for h in df_full["source_debt"].unique() if h)
        cats = [c for c in sorted(df_full["category"].unique()) if c in CATEGORY_CONFIG]
        cat_options = [{"label": CATEGORY_CONFIG[c]["label"], "value": c} for c in cats]
        return (
            _options(months),
            _options(holders),
            holders,
            cat_options,
            cats,
            f"Total database records: {len(df_full):,} transactions",
            banner,
        )

    @app.callback(Output("months", "value"), Input("period", "value"), Input("months", "options"))
    def apply_period(period, month_options):
        all_months = [o["value"] for o in month_options or []]
        return resolve_default_months(period, all_months)

    @app.callback(
        Output("filters", "data"),
        Input("months", "value"),
        Input("holders", "value"),
        Input("categories", "value"),
        Input("tx-type", "value"),
        Input("installment-type", "value"),
        Input("search-id", "value"),
    )
    def collect_filters(months, holders, categories, tx_type, installment_type, search):
        return {
            **DEFAULT_FILTERS,
            "selected_months": months or [],
            "selected_holders": holders or [],
            "selected_categories": categories or [],
            "tx_type": tx_type,
            "installment_type": installment_type,
            "search_id": search or "",
        }

    # ------------------------------------------------------------------ theme / privacy
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
            document.documentElement.dataset.theme = theme || 'dark';
            document.documentElement.classList.toggle('hide-amounts', (hide || []).length > 0);
            return window.dash_clientside.no_update;
        }
        """,
        Output("app-root", "className"),
        Input("theme", "data"),
        Input("hide-toggle", "value"),
    )

    @app.callback(*[Output(f"panel-{key}", "style") for key, _ in TABS], Input("tabs", "value"))
    def show_panel(active):
        return [{} if key == active else {"display": "none"} for key, _ in TABS]

    # ------------------------------------------------------------------ tab content
    def _guard(tab: str, active: str):
        if active != tab:
            raise PreventUpdate

    def _frames(filters: dict | None) -> tuple[pd.DataFrame, pd.DataFrame]:
        df_full = data_loader()
        return df_full, apply_filters(df_full, filters or DEFAULT_FILTERS)

    def _render(tab: str, active, theme, hide, build):
        _guard(tab, active)
        try:
            with chart_context(theme_base=theme or "dark", hide_amounts=bool(hide)):
                return build()
        except Exception:
            logger.exception("Failed to render tab %s", tab)
            return [
                html.Div(
                    "⚠️ Could not render this tab. See the server log.", className="alert critical"
                )
            ]

    common = (
        Input("filters", "data"),
        Input("theme", "data"),
        Input("hide-toggle", "value"),
        Input("tabs", "value"),
    )

    @app.callback(
        Output("content-dashboard", "children"),
        *common,
        Input("timeline", "value"),
        Input("chart-style", "value"),
    )
    def render_dashboard(filters, theme, hide, active, timeline, chart_style):
        def build():
            df_full, df_filtered = _frames(filters)
            return build_dashboard_view(
                df_filtered, df_full, group_col=timeline, chart_style=chart_style
            )

        return _render("dashboard", active, theme, hide, build)

    @app.callback(Output("content-trends", "children"), *common)
    def render_trends(filters, theme, hide, active):
        def build():
            df_full, df_filtered = _frames(filters)
            return build_trends_view(df_filtered, df_full)

        return _render("trends", active, theme, hide, build)

    @app.callback(
        Output("category-detail", "options"),
        Output("category-detail", "value"),
        Input("filters", "data"),
        State("category-detail", "value"),
    )
    def update_category_selector(filters, current):
        _, df_filtered = _frames(filters)
        if df_filtered.empty:
            return [], None
        options = category_options(df_filtered)
        values = [o["value"] for o in options]
        return options, current if current in values else (values[0] if values else None)

    @app.callback(
        Output("content-category", "children"), *common, Input("category-detail", "value")
    )
    def render_category(filters, theme, hide, active, category):
        def build():
            _, df_filtered = _frames(filters)
            return build_category_view(df_filtered, category)

        return _render("category", active, theme, hide, build)

    @app.callback(Output("content-reports", "children"), *common, Input("ref-limit", "value"))
    def render_reports(filters, theme, hide, active, ref_limit):
        def build():
            df_full, df_filtered = _frames(filters)
            return build_reports_view(df_filtered, df_full, ref_limit)

        return _render("reports", active, theme, hide, build)

    @app.callback(
        Output("download-csv", "data"),
        Input("download-btn", "n_clicks"),
        State("filters", "data"),
        prevent_initial_call=True,
    )
    def download_csv(_clicks, filters):
        _, df_filtered = _frames(filters)
        if df_filtered.empty:
            raise PreventUpdate
        filename, content = export_csv(df_filtered)
        return {"content": content, "filename": filename, "type": "text/csv"}

    return app


__all__ = ["create_app", "create_layout"]
