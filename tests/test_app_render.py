"""Renders the full Streamlit app headlessly (AppTest) on a synthetic Silver frame and checks that
no tab raises. Every database entrypoint is replaced — nothing touches MySQL."""

import importlib
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

MAIN_SCRIPT = str(Path(__file__).resolve().parents[1] / "main.py")

EXPECTED_TABS = [
    "📊 Overview",
    "📈 Trends",
    "🔔 Watchlist",
    "🔍 Categories",
    "📑 Reports",
    "📥 Ingest",
    "🏷️ Categorize",
    "🛠️ Manage Data",
]


def _empty(*_args, **_kwargs):
    return pd.DataFrame()


@pytest.fixture
def offline_app(monkeypatch):
    """Returns a factory: ``offline_app(silver_frame)`` -> AppTest for main.py with no DB."""

    def _factory(silver: pd.DataFrame) -> AppTest:
        database = importlib.import_module("src.expenses.database")
        monkeypatch.setattr(database, "get_db_engine", lambda *_a, **_k: object())
        monkeypatch.setattr(database, "load_expenses_data", lambda: silver)
        categorize = importlib.import_module("src.expenses.ui.tabs.categorize_tab")
        management = importlib.import_module("src.expenses.ui.tabs.management")
        for module in (categorize, management):
            monkeypatch.setattr(module, "get_db_engine", lambda *_a, **_k: None)
            monkeypatch.setattr(module, "load_bronze_data", _empty)
            monkeypatch.setattr(module, "load_silver_data", _empty)
        monkeypatch.setattr(categorize, "create_medallion_tables", lambda *_a, **_k: None)
        monkeypatch.setattr(management, "load_raw_data", _empty)
        return AppTest.from_file(MAIN_SCRIPT, default_timeout=60)

    return _factory


def test_all_tabs_render_with_data(offline_app, silver_history_df):
    at = offline_app(silver_history_df).run()
    assert not at.exception, [e.message for e in at.exception]
    assert [t.label for t in at.tabs][: len(EXPECTED_TABS)] == EXPECTED_TABS
    # One KPI row per analytic tab: Overview/Trends/Watchlist/Categories 4 each, Reports 3.
    assert len(at.metric) == 4 * 4 + 3


def test_app_renders_without_data(offline_app):
    at = offline_app(pd.DataFrame()).run()
    assert not at.exception, [e.message for e in at.exception]
    assert any("No data found" in w.value for w in at.warning)
