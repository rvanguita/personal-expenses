"""Dash frontend entrypoint: ``uv run python dash_main.py`` (port from DASH_PORT, default 8050)."""

from src.expenses.config import DASH_HOST, DASH_PORT
from src.expenses.dash_ui import create_app

app = create_app()
server = app.server  # WSGI entrypoint, e.g. `gunicorn dash_main:server`

if __name__ == "__main__":
    app.run(host=DASH_HOST, port=DASH_PORT, debug=False)
