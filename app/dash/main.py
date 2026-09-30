"""Dash entrypoint. From the repo root: ``uv run --directory app/dash python main.py``."""

from expenses.config import DASH_PORT
from expenses_dash import create_app


def main() -> None:
    create_app().run(host="0.0.0.0", port=DASH_PORT, debug=False)


if __name__ == "__main__":
    main()
