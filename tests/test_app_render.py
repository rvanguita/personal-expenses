"""Renders the Streamlit app headlessly (AppTest) on synthetic frames and checks that neither page
raises. Every database entrypoint is replaced — nothing touches MySQL."""

import importlib
from pathlib import Path

import pandas as pd
import pytest
from streamlit.proto.Dataframe_pb2 import Dataframe as DataframeProto
from streamlit.testing.v1 import AppTest

from src.expenses.parser import parse_raw_csv, transform_raw_to_bronze

MAIN_SCRIPT = str(Path(__file__).resolve().parents[1] / "main.py")

DATA_TABS = ["Importar", "Categorizar", "Gerenciar"]

SILVER_LAYER_COLUMNS = [
    "date",
    "date_buy",
    "id",
    "source_debt",
    "cost",
    "installment",
    "total_installments",
    "category",
]


def _returning(frame: pd.DataFrame | None):
    return lambda *_args, **_kwargs: frame.copy() if frame is not None else pd.DataFrame()


def _data_page(df_full):
    from src.expenses.ui.data_page import render_data

    render_data(df_full, object())


@pytest.fixture
def offline_app(monkeypatch):
    """Factory: ``offline_app(analytics_frame, raw=, bronze=, silver_layer=)`` -> AppTest for
    ``main.py`` with every DB read stubbed. ``analytics_frame`` feeds ``load_expenses_data``; the
    layer frames feed the Categorize / Manage Data tabs (empty when omitted)."""

    def _factory(
        silver: pd.DataFrame,
        *,
        raw: pd.DataFrame | None = None,
        bronze: pd.DataFrame | None = None,
        silver_layer: pd.DataFrame | None = None,
        page: str = "dashboard",
    ) -> AppTest:
        database = importlib.import_module("src.expenses.database")
        monkeypatch.setattr(database, "get_db_engine", lambda *_a, **_k: object())
        monkeypatch.setattr(database, "load_expenses_data", lambda: silver)
        categorizer = importlib.import_module("src.expenses.ai_categorizer")
        monkeypatch.setattr(categorizer, "get_db_engine", lambda *_a, **_k: None)
        monkeypatch.setattr(categorizer, "create_medallion_tables", lambda *_a, **_k: None)
        categorize = importlib.import_module("src.expenses.ui.tabs.categorize_tab")
        management = importlib.import_module("src.expenses.ui.tabs.management")
        for module in (categorize, management):
            monkeypatch.setattr(module, "get_db_engine", lambda *_a, **_k: None)
            monkeypatch.setattr(module, "load_bronze_data", _returning(bronze))
            monkeypatch.setattr(module, "load_silver_data", _returning(silver_layer))
        monkeypatch.setattr(categorize, "create_medallion_tables", lambda *_a, **_k: None)
        monkeypatch.setattr(management, "load_raw_data", _returning(raw))
        if page == "dados":
            # st.navigation pages are callables, which AppTest.switch_page can't reach.
            return AppTest.from_function(_data_page, args=(silver,), default_timeout=60)
        return AppTest.from_file(MAIN_SCRIPT, default_timeout=60)

    return _factory


def test_dashboard_renders_with_data(offline_app, silver_history_df):
    at = offline_app(silver_history_df).run()
    assert not at.exception, [e.message for e in at.exception]
    # One row of four KPIs, the three filters, and the largest-purchases table.
    assert len(at.metric) == 4
    assert [s.label for s in at.selectbox] == ["Período"]
    assert [m.label for m in at.multiselect] == ["Titular", "Categoria"]
    assert len(at.dataframe) == 1


def test_dashboard_filters_rerun(offline_app, silver_history_df):
    at = offline_app(silver_history_df).run()
    at.selectbox(key="dash_period").select("All History").run()
    at.multiselect(key="dash_categories").select("food").run()
    assert not at.exception, [e.message for e in at.exception]
    assert len(at.metric) == 4


def test_app_renders_without_data(offline_app):
    at = offline_app(pd.DataFrame()).run()
    assert not at.exception, [e.message for e in at.exception]
    assert any("Nenhum dado encontrado" in w.value for w in at.warning)


def test_operation_tabs_render_with_layer_data(offline_app, silver_history_df, sample_csv_file):
    raw = parse_raw_csv(sample_csv_file)
    bronze = transform_raw_to_bronze(raw)
    silver_layer = silver_history_df[SILVER_LAYER_COLUMNS].assign(
        motivation="", categorized_by="history_match"
    )

    at = offline_app(
        silver_history_df, raw=raw, bronze=bronze, silver_layer=silver_layer, page="dados"
    ).run()

    assert not at.exception, [e.message for e in at.exception]
    assert [t.label for t in at.tabs][: len(DATA_TABS)] == DATA_TABS
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Total Bronze"] == f"{len(bronze):,}"
    assert metrics["Total Silver Records"] == f"{len(silver_layer):,}"
    # AppTest exposes st.data_editor as a "dataframe" whose editing mode is not READ_ONLY. Both
    # Silver editors (Categorize + Manage Data) must be FIXED: saves merge edits into the full
    # table by row, so adding/deleting rows through the editor is not supported.
    editors = [df for df in at.dataframe if df.proto.editing_mode != DataframeProto.READ_ONLY]
    assert [df.proto.editing_mode for df in editors] == [DataframeProto.FIXED] * 2
