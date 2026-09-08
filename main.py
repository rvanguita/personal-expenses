# %%
import streamlit as st

from src.expenses.database import get_db_engine, load_expenses_data
from src.expenses.filters import apply_filters
from src.expenses.ui import (
    apply_custom_styles,
    render_amount_visibility_css,
    render_header,
    render_sidebar,
)
from src.expenses.ui.tabs import (
    render_categorize_tab,
    render_category_tab,
    render_dashboard_tab,
    render_import_tab,
    render_management_tab,
    render_reports_tab,
    render_trends_tab,
)


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
            "No data found in the database. Use the **Ingest Invoices** tab to upload your first invoice."
        )

    # Sidebar global filters
    filters = render_sidebar(df_full)

    # Global "hide amounts" privacy toggle (blurs monetary figures via injected CSS)
    render_amount_visibility_css(st.session_state.get("hide_amounts", False))

    # Applying filters (src.expenses.filters.apply_filters)
    df_filtered = apply_filters(df_full, filters)

    # Main navigation tabs
    (
        tab_dashboard,
        tab_trends,
        tab_categories,
        tab_reports,
        tab_ingest,
        tab_categorize,
        tab_manage,
    ) = st.tabs(
        [
            "📊 General Dashboard",
            "📈 Trends & Insights",
            "🔍 Category Analysis",
            "📑 Reports & Projections",
            "📥 Ingest Invoices (Raw & Bronze)",
            "🏷️ AI Categorization & Matching",
            "🛠️ Lakehouse Data Management",
        ]
    )

    with tab_dashboard:
        render_dashboard_tab(df_filtered, df_full)

    with tab_trends:
        render_trends_tab(df_filtered, df_full)

    with tab_categories:
        render_category_tab(df_filtered)

    with tab_reports:
        render_reports_tab(df_filtered, df_full)

    with tab_ingest:
        render_import_tab(engine)

    with tab_categorize:
        render_categorize_tab(engine)

    with tab_manage:
        render_management_tab(df_full, engine)


if __name__ == "__main__":
    main()
