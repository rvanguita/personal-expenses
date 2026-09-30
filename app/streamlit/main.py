"""Streamlit entrypoint. From the repo root: ``uv run --directory app/streamlit streamlit run main.py``.

Run from this folder so Streamlit picks up ``.streamlit/config.toml`` (theme, port 8503).
"""

from expenses_streamlit.app import main

main()
