"""Streamlit app entrypoint.

Run from the repo root with ``uv run --directory app/streamlit streamlit run main.py`` (port 8503);
Streamlit reads ``.streamlit/config.toml`` from the current directory, i.e. this folder.
"""

import sys
from pathlib import Path

# `streamlit run` / `python main.py` only put this folder on sys.path; the shared backend
# (`src.expenses`) and this app's package (`app.*`) are imported from the project root.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from app.streamlit.ui import (
    apply_custom_styles,
    render_amount_visibility_css,
    render_header,
    render_sidebar,
)
from app.streamlit.ui.tabs import (
    render_categorize_tab,
    render_category_tab,
    render_dashboard_tab,
    render_import_tab,
    render_management_tab,
    render_reports_tab,
    render_trends_tab,
    render_watchlist_tab,
)
from src.expenses.database import get_db_engine, load_expenses_data
from src.expenses.filters import apply_filters


def main():
    st.set_page_config(
        page_title="Expenses & Financial Intelligence",
        page_icon="💳",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    apply_custom_styles()
    render_header()

    engine = get_db_engine()
    if engine is None:
        st.error(
            "⚠️ Database configuration not found in `.env` file. Please check `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`."
        )
        return

    df_full = load_expenses_data()

    if df_full.empty:
        st.warning(
            "No data found in the database. Use **Data → Ingest** to upload your first invoice."
        )

    # Sidebar global filters
    filters = render_sidebar(df_full)

    # Global "hide amounts" privacy toggle (blurs monetary figures via injected CSS)
    render_amount_visibility_css(st.session_state.get("hide_amounts", False))

    # Applying filters (src.expenses.filters.apply_filters)
    df_filtered = apply_filters(df_full, filters)

    # Analysis first (one question per tab), then every write path grouped under "Data"
    tab_overview, tab_trends, tab_watchlist, tab_categories, tab_reports, tab_data = st.tabs(
        ["Overview", "Trends", "Watchlist", "Categories", "Reports", "Data"]
    )

    with tab_overview:
        render_dashboard_tab(df_filtered, df_full)

    with tab_trends:
        render_trends_tab(df_filtered, df_full)

    with tab_watchlist:
        render_watchlist_tab(df_filtered, df_full)

    with tab_categories:
        render_category_tab(df_filtered)

    with tab_reports:
        render_reports_tab(df_filtered, df_full)

    with tab_data:
        tab_ingest, tab_categorize, tab_manage = st.tabs(["Ingest", "Categorize", "Manage"])
        with tab_ingest:
            render_import_tab(engine)
        with tab_categorize:
            render_categorize_tab(engine)
        with tab_manage:
            render_management_tab(df_full, engine)


if __name__ == "__main__":
    main()
