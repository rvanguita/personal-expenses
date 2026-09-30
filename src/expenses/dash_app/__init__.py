"""Read-only Dash dashboard: how much was spent, where, and what is already committed.

Framework pieces: `theme` (tokens), `data` (view model over `analytics.py`), `figures` (Plotly),
`layout` (static structure) and `callbacks`. Styles live in the repo-level `assets/` folder.
"""

from collections.abc import Callable
from pathlib import Path

import pandas as pd
from dash import Dash

from src.expenses.dash_app.callbacks import register_callbacks, update_dashboard
from src.expenses.dash_app.data import build_view, filter_options, kpi_cards
from src.expenses.dash_app.layout import build_layout

ASSETS_DIR = Path(__file__).resolve().parents[3] / "assets"


def create_app(loader: Callable[[], pd.DataFrame] | None = None) -> Dash:
    """Builds the app. ``loader`` returns the Silver frame (defaults to ``load_expenses_data``,
    imported lazily so importing this package never touches the database)."""
    if loader is None:
        from src.expenses.database import load_expenses_data

        loader = load_expenses_data

    app = Dash(__name__, title="Despesas", assets_folder=str(ASSETS_DIR))
    # Layout as a function: filter options are rebuilt from fresh data on every page load.
    app.layout = lambda: build_layout(filter_options(loader()))
    register_callbacks(app, loader)
    return app


__all__ = ["build_view", "create_app", "filter_options", "kpi_cards", "update_dashboard"]
