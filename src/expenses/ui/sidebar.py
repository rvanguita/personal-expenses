import pandas as pd
import streamlit as st

from src.expenses.config import CATEGORY_CONFIG, LABEL_TO_CAT
from src.expenses.runtime import clear_caches
from src.expenses.ui.styles import render_theme_toggle


def render_sidebar(df_full: pd.DataFrame) -> dict:
    """Renders the sidebar controls and returns user-selected filter parameters."""
    with st.sidebar:
        st.markdown("### ⚙️ Dashboard Filters")

        # Global display controls — always shown, not part of the returned filter dict.
        render_theme_toggle()
        st.toggle(
            "🙈 Hide amounts",
            key="hide_amounts",
            help="Blur every monetary figure on screen; hover a value to reveal it.",
        )
        st.divider()

        if not df_full.empty:
            all_year_months = sorted(df_full["year_month"].unique().tolist(), reverse=True)

            # Predefined Period Filter
            period_option = st.selectbox(
                "📅 Predefined Period:",
                options=[
                    "Last 6 months",
                    "Last 3 months",
                    "Last 12 months",
                    "All History",
                    "Custom",
                ],
                index=0,
            )

            if period_option == "Last 3 months":
                default_months = all_year_months[:3]
            elif period_option == "Last 6 months":
                default_months = all_year_months[:6]
            elif period_option == "Last 12 months":
                default_months = all_year_months[:12]
            elif period_option == "All History":
                default_months = all_year_months
            else:
                default_months = all_year_months[:6]

            selected_months = st.multiselect(
                "Selected Invoices (Year-Month):",
                options=all_year_months,
                default=default_months,
            )

            st.divider()

            # Cardholder Filter (Portador)
            all_holders = sorted([h for h in df_full["source_debt"].unique() if h])
            selected_holders = []
            if all_holders:
                selected_holders = st.multiselect(
                    "👤 Cardholder (Portador):",
                    options=all_holders,
                    default=all_holders,
                )

            st.divider()

            # Category Filter
            all_cat_labels = [
                CATEGORY_CONFIG[cat]["label"]
                for cat in sorted(df_full["category"].unique())
                if cat in CATEGORY_CONFIG
            ]

            col_btn1, col_btn2 = st.columns(2)
            if col_btn1.button("Select All", use_container_width=True):
                st.session_state["selected_cats"] = all_cat_labels
            if col_btn2.button("Deselect All", use_container_width=True):
                st.session_state["selected_cats"] = []

            if "selected_cats" not in st.session_state:
                st.session_state["selected_cats"] = all_cat_labels

            selected_cat_labels = st.multiselect(
                "🏷️ Categories:",
                options=all_cat_labels,
                default=[c for c in st.session_state["selected_cats"] if c in all_cat_labels],
            )
            selected_categories = [
                LABEL_TO_CAT[cat_lbl] for cat_lbl in selected_cat_labels if cat_lbl in LABEL_TO_CAT
            ]

            st.divider()

            # Transaction Type Filter (Net Expenses, Gross, Refunds, All)
            tx_type = st.radio(
                "Transaction Type:",
                options=[
                    "Net Expenses (Purchases - Refunds)",
                    "Gross Purchases Only (Positive)",
                    "Refunds Only (Negative)",
                    "All Transactions",
                ],
                index=0,
            )

            installment_type = st.selectbox(
                "Payment Method:",
                options=["All", "Single Payment Only", "Installments Only"],
                index=0,
            )

            search_id = st.text_input(
                "🔍 Search Merchant:", placeholder="E.g.: Example Market, Demo Transit..."
            )

            st.divider()
            if st.button("🔄 Refresh / Clear Cache", use_container_width=True):
                clear_caches()
                st.rerun()

            st.caption(f"Total database records: **{len(df_full):,}** transactions")
            return {
                "selected_months": selected_months,
                "selected_holders": selected_holders,
                "selected_categories": selected_categories,
                "tx_type": tx_type,
                "installment_type": installment_type,
                "search_id": search_id,
            }

        return {
            "selected_months": [],
            "selected_holders": [],
            "selected_categories": [],
            "tx_type": "Net Expenses (Purchases - Refunds)",
            "installment_type": "All",
            "search_id": "",
        }
