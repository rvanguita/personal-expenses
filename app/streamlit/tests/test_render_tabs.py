"""Each Streamlit tab / sidebar renderer run on its own inside AppTest (synthetic data, no DB)."""

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from expenses.analytics import (
    calculate_kpis,
    get_period_over_period_comparison,
    get_spending_trend,
    get_year_over_year_comparison,
)


def _call(module, func, *args):
    import importlib

    getattr(importlib.import_module(module), func)(*args)


def _run(module, func, *args) -> AppTest:
    at = AppTest.from_function(_call, args=(module, func, *args), default_timeout=60).run()
    assert not at.exception, [e.message for e in at.exception]
    return at


TABS = "expenses_streamlit.tabs"


@pytest.fixture
def frames(silver_history_df):
    months = sorted(silver_history_df["year_month"].unique())[-6:]
    filtered = silver_history_df[
        silver_history_df["year_month"].isin(months) & ~silver_history_df["is_payment"]
    ]
    return filtered, silver_history_df


def test_render_dashboard_tab(frames):
    at = _run(f"{TABS}.dashboard", "render_dashboard_tab", *frames)
    assert [m.label for m in at.metric][:3] == ["Net spent", "Monthly average", "Latest invoice"]
    assert _run(f"{TABS}.dashboard", "render_dashboard_tab", pd.DataFrame(), frames[1]).info


def test_dashboard_render_kpis(frames):
    filtered, full = frames
    at = _run(f"{TABS}.dashboard", "_render_kpis", calculate_kpis(filtered, full), full)
    assert len(at.metric) == 4


def test_render_trends_tab_and_parts(frames):
    filtered, full = frames
    assert len(_run(f"{TABS}.trends", "render_trends_tab", *frames).metric) == 4
    months = sorted(filtered["year_month"].unique())
    pop = get_period_over_period_comparison(full, months)
    trend = get_spending_trend(filtered)
    assert len(_run(f"{TABS}.trends", "_render_kpis", trend, pop).metric) == 4
    at = _run(f"{TABS}.trends", "_render_comparison", pop, get_year_over_year_comparison(full))
    assert at.get("plotly_chart")


def test_render_watchlist_tab(frames):
    at = _run(f"{TABS}.watchlist", "render_watchlist_tab", *frames)
    assert [m.label for m in at.metric][0] == "Fixed monthly cost"


def test_render_category_tab(frames):
    at = _run(f"{TABS}.category", "render_category_tab", frames[0])
    assert at.selectbox[0].label == "Category" and len(at.metric) == 4


def test_render_reports_tab_and_parts(frames):
    filtered, full = frames
    assert len(_run(f"{TABS}.reports", "render_reports_tab", *frames).metric) == 3
    assert len(_run(f"{TABS}.reports", "_render_commitments", full).metric) == 3
    at = _run(f"{TABS}.reports", "_render_export", filtered, filtered)
    assert at.get("download_button")


def test_render_sidebar(silver_history_df):
    at = _run("expenses_streamlit.sidebar", "render_sidebar", silver_history_df)
    assert [s.label for s in at.sidebar.selectbox] == ["Period", "Payment method"]
    assert "Cardholder" in [m.label for m in at.sidebar.multiselect]
    assert _run("expenses_streamlit.sidebar", "render_sidebar", pd.DataFrame()).sidebar


@pytest.fixture
def no_layer_data(monkeypatch):
    import expenses_streamlit.tabs.categorize_tab as categorize
    import expenses_streamlit.tabs.management as management

    empty = lambda *_a, **_k: pd.DataFrame()  # noqa: E731
    for module in (categorize, management):
        monkeypatch.setattr(module, "get_db_engine", lambda *_a, **_k: None)
        monkeypatch.setattr(module, "load_bronze_data", empty)
        monkeypatch.setattr(module, "load_silver_data", empty)
    monkeypatch.setattr(categorize, "create_medallion_tables", lambda *_a, **_k: None)
    monkeypatch.setattr(management, "load_raw_data", empty)


def test_render_management_categorize_and_import_tabs(no_layer_data, silver_history_df):
    assert _run(f"{TABS}.management", "render_management_tab", silver_history_df, None)
    at = _run(f"{TABS}.categorize_tab", "render_categorize_tab", None)
    assert "No records found in the Bronze layer" in at.info[0].value
    assert _run(f"{TABS}.import_tab", "render_import_tab", None)
