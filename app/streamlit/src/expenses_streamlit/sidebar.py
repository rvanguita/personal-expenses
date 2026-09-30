import pandas as pd
import streamlit as st

from expenses.config import CATEGORY_CONFIG, LABEL_TO_CAT
from expenses.filters import (
    DEFAULT_FILTERS,
    INSTALLMENT_OPTIONS,
    PERIOD_OPTIONS,
    TX_TYPE_OPTIONS,
    resolve_default_months,
)
from expenses.runtime import clear_caches


def render_sidebar(df_full: pd.DataFrame) -> dict:
    """Renders the sidebar controls and returns user-selected filter parameters."""
    with st.sidebar:
        st.markdown("### Filters")

        if not df_full.empty:
            all_year_months = sorted(df_full["year_month"].unique().tolist(), reverse=True)

            period_option = st.selectbox("Period", options=PERIOD_OPTIONS, index=0)
            selected_months = resolve_default_months(period_option, all_year_months)
            if period_option == "Custom":
                selected_months = st.multiselect(
                    "Invoices", options=all_year_months, default=selected_months
                )

            # Cardholder Filter (Portador)
            all_holders = sorted([h for h in df_full["source_debt"].unique() if h])
            selected_holders = []
            if all_holders:
                selected_holders = st.multiselect(
                    "Cardholder", options=all_holders, placeholder="All cardholders"
                )

            # Category Filter
            all_cat_labels = [
                CATEGORY_CONFIG[cat]["label"]
                for cat in sorted(df_full["category"].unique())
                if cat in CATEGORY_CONFIG
            ]
            selected_cat_labels = st.multiselect(
                "Categories", options=all_cat_labels, placeholder="All categories"
            )
            selected_categories = [
                LABEL_TO_CAT[cat_lbl] for cat_lbl in selected_cat_labels if cat_lbl in LABEL_TO_CAT
            ]

            with st.expander("More filters"):
                tx_type = st.radio(
                    "Transaction type",
                    options=TX_TYPE_OPTIONS,
                    index=0,
                )
                installment_type = st.selectbox(
                    "Payment method",
                    options=INSTALLMENT_OPTIONS,
                    index=0,
                )
                search_id = st.text_input(
                    "Search merchant", placeholder="E.g.: Example Market, Demo Transit..."
                )

            with st.expander("Display"):
                st.toggle(
                    "Hide amounts",
                    key="hide_amounts",
                    help="Blur every monetary figure on screen; hover a value to reveal it.",
                )
                if st.button("Reload data", width="stretch"):
                    clear_caches()
                    st.rerun()

            st.caption(f"{len(df_full):,} transactions in the database")
            return {
                "selected_months": selected_months,
                "selected_holders": selected_holders,
                "selected_categories": selected_categories,
                "tx_type": tx_type,
                "installment_type": installment_type,
                "search_id": search_id,
            }

        return dict(DEFAULT_FILTERS)
