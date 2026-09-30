"""Import smoke: every Streamlit module imports with no database work at import time."""

import importlib

import pytest

TAB_MODULES = [
    "dashboard",
    "trends",
    "watchlist",
    "category",
    "reports",
    "import_tab",
    "categorize_tab",
    "management",
]
RENDER_FUNCS = [f"render_{name}_tab" for name in TAB_MODULES]
RENDER_FUNCS[TAB_MODULES.index("import_tab")] = "render_import_tab"
RENDER_FUNCS[TAB_MODULES.index("categorize_tab")] = "render_categorize_tab"


@pytest.mark.parametrize("module", ["app", "charts", "figures", "insights", "sidebar", "styles"])
def test_module_imports(no_db, module):
    importlib.import_module(f"expenses_streamlit.{module}")


@pytest.mark.parametrize("tab", TAB_MODULES)
def test_tab_module_imports(no_db, tab):
    importlib.import_module(f"expenses_streamlit.tabs.{tab}")


def test_render_functions_exposed(no_db):
    tabs = importlib.import_module("expenses_streamlit.tabs")
    for name in RENDER_FUNCS:
        assert callable(getattr(tabs, name)), name
    assert callable(importlib.import_module("expenses_streamlit.app").main)
