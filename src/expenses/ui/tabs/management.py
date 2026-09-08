import pandas as pd
import streamlit as st

from src.expenses.config import (
    CATEGORY_CONFIG,
    MYSQL_DB_SILVER,
    load_category_dictionary,
)
from src.expenses.database import (
    deduplicate_all_layers,
    get_db_engine,
    load_bronze_data,
    load_raw_data,
    load_silver_data,
    save_dataframe_replace,
)
from src.expenses.runtime import clear_caches


def render_management_tab(df_full: pd.DataFrame, engine=None):
    """Renders the Medallion Data Lakehouse record editor, deduplication tool, and category dictionary viewer tab."""
    st.markdown("### 🛠️ Lakehouse Data Management (Raw, Bronze, Silver)")
    st.caption(
        "Inspect and manage database records across the Medallion databases or view the category dictionary."
    )

    col_btn_dedup, col_btn_refresh = st.columns([2, 1])
    with col_btn_dedup:
        if st.button(
            "🧹 Deduplicate All Layers (Drop Duplicate Rows)",
            type="secondary",
            use_container_width=True,
        ):
            with st.spinner(
                "Scanning and removing duplicate records from Raw, Bronze, and Silver layers..."
            ):
                dropped = deduplicate_all_layers()
                st.success(
                    f"✅ Deduplication completed! Dropped {dropped['raw']} in Raw, {dropped['bronze']} in Bronze, and {dropped['silver']} in Silver."
                )
                st.rerun()

    with col_btn_refresh:
        if st.button("🔄 Refresh Lakehouse Cache", use_container_width=True):
            clear_caches()
            st.rerun()

    st.write("")

    tab_silver, tab_bronze, tab_raw, tab_cat_edit = st.tabs(
        [
            "🥈 Silver Layer (Enriched & Categorized)",
            "🥉 Bronze Layer (Cleaned & Standardized)",
            "🧱 Raw Layer (Exact Input Strings)",
            "📚 Category Dictionary (JSON)",
        ]
    )

    # ------------------------------------
    # 1. SILVER LAYER (Direct editable)
    # ------------------------------------
    with tab_silver:
        st.markdown("#### 🥈 Silver Database Layer Editor")
        st.caption(
            "This is the enriched business layer displayed in the dashboard and analytics. You can edit categories and click 'Save Changes'."
        )

        df_silver = load_silver_data()
        if not df_silver.empty:
            df_for_edit = df_silver[
                [
                    "date",
                    "date_buy",
                    "id",
                    "cost",
                    "installment",
                    "total_installments",
                    "category",
                    "motivation",
                    "categorized_by",
                ]
            ].copy()

            # Prioritize 'not_found' / unclassified categories first, then sort by merchant name (A-Z), then latest dates
            df_for_edit["_is_not_found"] = (
                df_for_edit["category"]
                .fillna("")
                .astype(str)
                .str.lower()
                .isin(["not_found", "pending", "none", ""])
            )
            df_for_edit = (
                df_for_edit.sort_values(
                    by=["_is_not_found", "id", "date"], ascending=[False, True, False]
                )
                .drop(columns=["_is_not_found"])
                .reset_index(drop=True)
            )

            unclassified_count = int(
                df_silver["category"]
                .fillna("")
                .astype(str)
                .str.lower()
                .isin(["not_found", "pending", "none", ""])
                .sum()
            )

            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Total Silver Records", f"{len(df_silver):,}")
            col_m2.metric("Categorized", f"{len(df_silver) - unclassified_count:,}")
            col_m3.metric("⚠️ Uncategorized (`not_found`)", f"{unclassified_count:,}")

            if unclassified_count > 0:
                st.warning(
                    f"📌 **{unclassified_count} uncategorized transaction(s)** (`not_found`) are displayed at the top of the table below for quick review and classification."
                )

            df_edited = st.data_editor(
                df_for_edit,
                column_config={
                    "date": st.column_config.DateColumn("Invoice Date", format="YYYY-MM-DD"),
                    "date_buy": st.column_config.DateColumn("Purchase Date", format="YYYY-MM-DD"),
                    "id": st.column_config.TextColumn("Merchant / ID"),
                    "cost": st.column_config.NumberColumn("Amount (R$)", format="R$ %.2f"),
                    "installment": st.column_config.NumberColumn("Installment"),
                    "total_installments": st.column_config.NumberColumn("Total Installments"),
                    "category": st.column_config.SelectboxColumn(
                        "Category",
                        options=list(CATEGORY_CONFIG.keys()),
                        required=True,
                    ),
                    "motivation": st.column_config.TextColumn("Motivation"),
                    "categorized_by": st.column_config.TextColumn("Source", disabled=True),
                },
                use_container_width=True,
                num_rows="dynamic",
                key="silver_editor",
            )

            if st.button("💾 Save Changes to Silver Layer", type="primary", key="btn_save_silver"):
                with st.spinner("Updating Silver table in MySQL..."):
                    engine_silver = get_db_engine(MYSQL_DB_SILVER)
                    if engine_silver is not None:
                        save_dataframe_replace(df_edited, engine_silver, MYSQL_DB_SILVER)
                    clear_caches()
                    st.success("Silver layer successfully updated!")
                    st.rerun()
        else:
            st.info(
                "Silver table is currently empty. Ingest an invoice via the '📥 Ingest Invoices' tab."
            )

    # ------------------------------------
    # 2. BRONZE LAYER
    # ------------------------------------
    with tab_bronze:
        st.markdown("#### 🥉 Bronze Database Layer Records")
        st.caption(
            "Standardized transactions with numeric dot decimals, parsed dates, and English column headers."
        )
        df_bronze = load_bronze_data()
        if not df_bronze.empty:
            df_bronze_display = df_bronze.copy()
            df_bronze_display["date"] = pd.to_datetime(df_bronze_display["date"])
            df_bronze_display["date_buy"] = pd.to_datetime(df_bronze_display["date_buy"])
            df_bronze_display["cost"] = df_bronze_display["cost"].astype(float)
            st.dataframe(
                df_bronze_display,
                column_config={
                    "date": st.column_config.DateColumn("Invoice Date", format="YYYY-MM-DD"),
                    "date_buy": st.column_config.DateColumn("Purchase Date", format="YYYY-MM-DD"),
                    "id": st.column_config.TextColumn("Merchant ID"),
                    "source_debt": st.column_config.TextColumn("Cardholder"),
                    "cost": st.column_config.NumberColumn("Amount", format="R$ %.2f"),
                    "installment": st.column_config.NumberColumn("Installment"),
                    "total_installments": st.column_config.NumberColumn("Total Installments"),
                    "source_file": st.column_config.TextColumn("Source File"),
                    "created_at": st.column_config.DatetimeColumn(
                        "Ingested At", format="YYYY-MM-DD HH:mm:ss"
                    ),
                },
                use_container_width=True,
                hide_index=True,
            )
            st.caption(f"Total Bronze records: **{len(df_bronze):,}**")
        else:
            st.info("Bronze table is currently empty.")

    # ------------------------------------
    # 3. RAW LAYER
    # ------------------------------------
    with tab_raw:
        st.markdown("#### 🧱 Raw Database Layer Records")
        st.caption(
            "Exact source lines as uploaded from credit card CSV invoices, preserving original strings and commas."
        )
        df_raw = load_raw_data()
        if not df_raw.empty:
            st.dataframe(
                df_raw,
                column_config={col: st.column_config.TextColumn(col) for col in df_raw.columns},
                use_container_width=True,
                hide_index=True,
            )
            st.caption(f"Total Raw records: **{len(df_raw):,}**")
        else:
            st.info("Raw table is currently empty.")

    # ------------------------------------
    # 4. CATEGORY DICTIONARY
    # ------------------------------------
    with tab_cat_edit:
        st.markdown("#### 📖 Category Keywords & Motives Dictionary")
        try:
            cat_json = load_category_dictionary()
            st.json(cat_json, expanded=False)

            # Dictionary statistics
            terms_count = {k: len(v) for k, v in cat_json.items()}
            df_terms = pd.DataFrame(
                [
                    {
                        "Category": CATEGORY_CONFIG.get(k, {}).get("label", k),
                        "Identifier": k,
                        "Registered Motives": v,
                    }
                    for k, v in terms_count.items()
                ]
            ).sort_values(by="Category", ascending=True)

            st.write("##### Registered Motives Breakdown per Category")
            st.dataframe(
                df_terms,
                column_config={
                    "Category": st.column_config.TextColumn("Category"),
                    "Identifier": st.column_config.TextColumn("Identifier"),
                    "Registered Motives": st.column_config.NumberColumn(
                        "Registered Motives", format="%d"
                    ),
                },
                use_container_width=True,
                hide_index=True,
            )

        except Exception as e:
            st.error(f"Error loading category dictionary: {e}")
