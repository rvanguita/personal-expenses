"""Workspace layout and dependency boundaries between the backend and the two apps."""

import ast
import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APPS = ("streamlit", "dash")


def _top_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    return {
        (node.module if isinstance(node, ast.ImportFrom) else alias.name).split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom) and not getattr(node, "level", 0)
        for alias in node.names
    }


def _imports_under(folder: Path) -> set[str]:
    found: set[str] = set()
    for path in folder.rglob("*.py"):
        found |= _top_level_imports(path)
    return found


def test_backend_package_imports_and_reexports(no_db):
    mod = importlib.import_module("expenses")
    for name in ("load_expenses_data", "apply_filters", "normalize_merchant_id", "calculate_kpis"):
        assert callable(getattr(mod, name)), name


def test_backend_is_framework_free():
    imported = _imports_under(ROOT / "src" / "expenses")
    assert not imported & {"streamlit", "dash", "expenses_streamlit", "expenses_dash"}


def test_apps_do_not_import_each_other():
    assert not _imports_under(ROOT / "app" / "dash") & {"streamlit", "expenses_streamlit"}
    assert "expenses_dash" not in _imports_under(ROOT / "app" / "streamlit")


@pytest.mark.parametrize("app", APPS)
def test_app_folder_layout(app):
    folder = ROOT / "app" / app
    for name in ("pyproject.toml", "Dockerfile", "main.py"):
        assert (folder / name).is_file(), name
    assert (folder / "src" / f"expenses_{app}" / "__init__.py").is_file()
    assert any((folder / "tests").glob("test_*.py"))
