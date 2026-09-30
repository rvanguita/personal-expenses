"""Framework-agnostic dashboard layer shared by the Streamlit (`main.py`) and Dash (`dash_app.py`)
frontends: view model (`data`), Plotly figures (`figures`) and design tokens (`theme`).
Must never import Streamlit or Dash."""

from src.expenses.dashboard.data import (
    DEFAULT_PERIOD,
    PERIOD_LABELS,
    DashboardView,
    build_view,
    filter_options,
    kpi_cards,
    month_label,
)
from src.expenses.dashboard.figures import (
    all_figures,
    commitments_figure,
    empty_figure,
    monthly_figure,
    ranked_bar_figure,
)

__all__ = [
    "DEFAULT_PERIOD",
    "PERIOD_LABELS",
    "DashboardView",
    "all_figures",
    "build_view",
    "commitments_figure",
    "empty_figure",
    "filter_options",
    "kpi_cards",
    "month_label",
    "monthly_figure",
    "ranked_bar_figure",
]
