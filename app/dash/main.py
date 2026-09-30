"""Dash app entrypoint (read-only dashboard).

Run from the repo root with ``uv run --directory app/dash python main.py`` (port ``DASH_PORT``).
"""

import sys
from pathlib import Path

# `streamlit run` / `python main.py` only put this folder on sys.path; the shared backend
# (`src.expenses`) and this app's package (`app.*`) are imported from the project root.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dash import create_app
from src.expenses.config import DASH_PORT


def main() -> None:
    create_app().run(host="0.0.0.0", port=DASH_PORT, debug=False)


if __name__ == "__main__":
    main()
