"""Guard: every module-level function in the backend and both apps is exercised by some test.

A function counts as tested when its name appears (as a whole word) in at least one test file.
Add a test when this fails — do not add the name to a skip list.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = [
    ROOT / "src" / "expenses",
    ROOT / "app" / "streamlit" / "src",
    ROOT / "app" / "dash" / "src",
]
TEST_DIRS = [ROOT / "tests", ROOT / "app" / "streamlit" / "tests", ROOT / "app" / "dash" / "tests"]


def _functions() -> dict[str, str]:
    found = {}
    for folder in SOURCE_DIRS:
        for path in folder.rglob("*.py"):
            for node in ast.parse(path.read_text()).body:
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    found[f"{path.relative_to(ROOT)}::{node.name}"] = node.name
    return found


def test_every_function_has_a_test():
    tests_text = "\n".join(
        p.read_text()
        for folder in TEST_DIRS
        for p in folder.rglob("*.py")
        if p.name != Path(__file__).name
    )
    untested = sorted(
        where
        for where, name in _functions().items()
        if not re.search(rf"\b{re.escape(name)}\b", tests_text)
    )
    assert not untested, "functions without tests:\n  " + "\n  ".join(untested)
