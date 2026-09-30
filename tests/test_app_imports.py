"""Build / import smoke tests — catch a broken import in the app or a tab module before it ships,
and assert the package and `main` do no database/Gemini work at import time."""

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

RENDER_FUNCS = [
    "render_dashboard_tab",
    "render_trends_tab",
    "render_watchlist_tab",
    "render_category_tab",
    "render_reports_tab",
    "render_import_tab",
    "render_categorize_tab",
    "render_management_tab",
]


def _boom(*_args, **_kwargs):
    raise AssertionError("database access happened at import time")


@pytest.fixture
def no_db(monkeypatch):
    """Any DB entrypoint touched during import fails loudly."""
    monkeypatch.setattr("src.expenses.database.get_db_engine", _boom)
    monkeypatch.setattr("src.expenses.database.create_medallion_tables", _boom)
    monkeypatch.setattr("src.expenses.database.ensure_databases_exist", _boom)


def test_package_imports_and_reexports(no_db):
    mod = importlib.import_module("src.expenses")
    for name in ("load_expenses_data", "apply_filters", "normalize_merchant_id", "calculate_kpis"):
        assert callable(getattr(mod, name)), name


def test_main_module_imports_without_running(no_db):
    main = importlib.import_module("main")
    assert callable(main.main)


@pytest.mark.parametrize("tab", TAB_MODULES)
def test_tab_module_imports(no_db, tab):
    importlib.import_module(f"src.expenses.ui.tabs.{tab}")


def test_all_render_funcs_exposed(no_db):
    tabs_pkg = importlib.import_module("src.expenses.ui.tabs")
    for fn in RENDER_FUNCS:
        assert callable(getattr(tabs_pkg, fn)), fn


def test_dash_entrypoint_imports_without_running(no_db):
    dash_app = importlib.import_module("dash_app")
    assert callable(dash_app.main)
    package = importlib.import_module("src.expenses.dash_app")
    assert callable(package.create_app)


def test_dash_package_does_not_import_streamlit():
    import ast
    from pathlib import Path

    for path in Path("src/expenses/dash_app").glob("*.py"):
        tree = ast.parse(path.read_text())
        imported = {
            (node.module if isinstance(node, ast.ImportFrom) else alias.name).split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import | ast.ImportFrom)
            for alias in node.names
        }
        assert "streamlit" not in imported, path
