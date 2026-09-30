"""Import smoke: the Dash package and its entrypoint import with no database work."""

import importlib
import importlib.util
from pathlib import Path

import pytest

MAIN = Path(__file__).resolve().parents[1] / "main.py"


@pytest.mark.parametrize(
    "module",
    ["", ".analyses", ".callbacks", ".data", ".figures", ".fmt", ".layout", ".pages", ".theme"],
)
def test_module_imports(no_db, module):
    importlib.import_module(f"expenses_dash{module}")


def test_entrypoint_loads_without_running(no_db):
    spec = importlib.util.spec_from_file_location("dash_entrypoint", MAIN)
    entry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entry)  # __name__ != "__main__": defines main() without serving
    assert callable(entry.main)


def test_assets_ship_inside_the_package():
    package = importlib.import_module("expenses_dash")
    assert (package.ASSETS_DIR / "dashboard.css").is_file()
