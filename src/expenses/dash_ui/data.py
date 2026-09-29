"""Data access for the Dash pages: one Silver loader, the shared filters and the cross-filter."""

import io
from collections.abc import Callable
from datetime import UTC, datetime

import pandas as pd

from src.expenses.database import load_expenses_data
from src.expenses.filters import DEFAULT_FILTERS, apply_filters

_loader: Callable[[], pd.DataFrame] = load_expenses_data


def configure(loader: Callable[[], pd.DataFrame]) -> None:
    """Sets the Silver-frame loader (injectable so tests/demos never touch MySQL)."""
    global _loader
    _loader = loader


def load_full() -> pd.DataFrame:
    return _loader()


MONTH_COLUMNS = ("year_month", "buy_year_month")


def apply_selection(
    df: pd.DataFrame,
    month: str | None = None,
    category: str | None = None,
    month_col: str = "year_month",
) -> pd.DataFrame:
    """Cross-filter: narrows a frame to the clicked month (invoice or purchase) and/or category."""
    if df.empty:
        return df
    if month and month_col in MONTH_COLUMNS:
        df = df[df[month_col] == month]
    if category:
        df = df[df["category"] == category]
    return df


def get_frames(filters: dict | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(df_full, df_filtered) for the sidebar/top-bar filter dict."""
    df_full = load_full()
    return df_full, apply_filters(df_full, filters or DEFAULT_FILTERS)


def export_csv(df: pd.DataFrame) -> dict:
    """``dcc.Download`` payload with the same CSV format as the Streamlit download."""
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, sep=";", encoding="utf-8-sig")
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    return {
        "content": buffer.getvalue(),
        "filename": f"relatorio_despesas_{stamp}.csv",
        "type": "text/csv",
    }
