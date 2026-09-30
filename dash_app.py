"""Dash frontend entrypoint (read-only dashboard). Run with ``uv run python dash_app.py``."""

from src.expenses.config import DASH_PORT
from src.expenses.dash_app import create_app


def main() -> None:
    create_app().run(host="0.0.0.0", port=DASH_PORT, debug=False)


if __name__ == "__main__":
    main()
