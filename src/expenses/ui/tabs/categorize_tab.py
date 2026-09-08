import pandas as pd
import sqlalchemy
import streamlit as st

from src.expenses.ai_categorizer import (
    match_merchants_with_history,
    repopulate_silver_layer,
)
from src.expenses.config import (
    CATEGORY_CONFIG,
    MYSQL_DB_SILVER,
    MYSQL_TABLE,
)
from src.expenses.database import (
    create_medallion_tables,
    get_db_engine,
    load_bronze_data,
    load_silver_data,
    save_dataframe_replace,
)
from src.expenses.runtime import clear_caches


def render_categorize_tab(engine=None):
    """Renders the dedicated Categorization, Batch Gemini AI (25 IDs), and Silver Repopulation tab."""
    st.markdown("### 🏷️ Smart AI Categorization & Silver Layer Enrichment")
    st.caption(
        "Evaluates records in the **Bronze** layer, automatically matches known merchant categories from history/dictionary, "
        "and sends unknown merchants in **batches of 25 unique IDs** to **Gemini AI**, saving progressively to the **Silver** database."
    )

    create_medallion_tables()
    engine_silver = get_db_engine(MYSQL_DB_SILVER)

    # 1. Fetch Bronze and Silver data to evaluate status
    df_bronze = load_bronze_data()
    if df_bronze.empty:
        st.info(
            "No records found in the Bronze layer. Please import an invoice in the '📥 Ingest Invoices' tab first."
        )
        return

    # Check existing Silver records to identify pending / unclassified transactions
    df_silver_existing = pd.DataFrame()
    if engine_silver is not None:
        with engine_silver.connect() as conn:
            try:
                df_silver_existing = pd.read_sql(
                    sqlalchemy.text(
                        f"SELECT date, date_buy, id, cost, installment, category FROM {MYSQL_TABLE}"
                    ),
                    conn,
                )
            except Exception:  # noqa: BLE001
                df_silver_existing = pd.DataFrame()

    # Identify pending transactions
    if not df_silver_existing.empty:
        df_silver_existing["key"] = (
            df_silver_existing["date"].astype(str)
            + "_"
            + df_silver_existing["date_buy"].astype(str)
            + "_"
            + df_silver_existing["id"].astype(str)
            + "_"
            + df_silver_existing["cost"].astype(str)
            + "_"
            + df_silver_existing["installment"].astype(str)
        )
        df_bronze_check = df_bronze.copy()
        df_bronze_check["key"] = (
            df_bronze_check["date"].astype(str)
            + "_"
            + df_bronze_check["date_buy"].astype(str)
            + "_"
            + df_bronze_check["id"].astype(str)
            + "_"
            + df_bronze_check["cost"].astype(str)
            + "_"
            + df_bronze_check["installment"].astype(str)
        )
        df_pending_bronze = df_bronze_check[
            ~df_bronze_check["key"].isin(df_silver_existing["key"])
        ].drop(columns=["key"], errors="ignore")
    else:
        df_pending_bronze = df_bronze.copy()

    # Smart Matching evaluation across Bronze records
    df_matched, df_unmatched = match_merchants_with_history(df_bronze, engine_silver)

    # -------------------------------------------------------------
    # Multi-Column Layout: Column 1 (Status) | Column 2 (Action Trigger)
    # -------------------------------------------------------------
    col_status, col_action = st.columns([1, 1], gap="large")

    with col_status:
        st.markdown("#### 📊 Silver Layer Status & Matching Metrics")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Bronze", f"{len(df_bronze):,}")
        m2.metric("Silver Published", f"{len(df_silver_existing):,}")
        m3.metric("Pending Sync", f"{len(df_pending_bronze):,}")

        st.markdown("##### 🔍 Merchant Match Breakdown:")
        st.success(
            f"🎯 **{len(df_matched)} merchant(s) recognized** (auto-inheriting categories from history & dictionary)."
        )
        if len(df_unmatched) > 0:
            num_batches_calc = (len(df_unmatched) + 24) // 25
            st.warning(
                f"🤖 **{len(df_unmatched)} unknown merchant(s)** (will be processed in **{num_batches_calc} batch(es)** of 25 IDs)."
            )
        else:
            st.info("✨ **0 pending AI merchants!** All records are mapped and categorized.")

    with col_action:
        st.markdown("#### ⚡ Batch Pipeline Trigger")
        st.caption(
            "Runs auto-matching + Gemini AI in batches of 25 IDs and progressively saves to the Silver database layer."
        )

        batch_size = st.number_input(
            "Unique IDs Batch Size (Gemini):", min_value=5, max_value=50, value=25, step=5
        )

        btn_run = st.button(
            f"🚀 Run Batch Categorization ({batch_size} IDs) & Sync to Silver",
            type="primary",
            use_container_width=True,
        )

        if btn_run:
            progress_bar = st.progress(0, text="Starting categorization pipeline...")
            status_text = st.empty()

            def update_progress(
                batch_num, total_batches, current_chunk_len, total_count, phase="calling"
            ):
                pct = int((batch_num / total_batches) * 100)
                if phase == "saved":
                    progress_bar.progress(
                        pct,
                        text=f"Batch {batch_num}/{total_batches} ({current_chunk_len} IDs) categorized & saved to Silver!",
                    )
                    status_text.success(
                        f"💾 Batch {batch_num} of {total_batches} successfully saved into Silver database."
                    )
                else:
                    progress_bar.progress(
                        max(0, pct - 5),
                        text=f"Processing batch {batch_num}/{total_batches} ({current_chunk_len} IDs)...",
                    )
                    status_text.info(
                        f"⏳ Sending batch {batch_num} of {total_batches} ({current_chunk_len} IDs) to Gemini AI..."
                    )

            with st.spinner("Processing categorization & progressive Silver database sync..."):
                res_repop = repopulate_silver_layer(
                    batch_size=batch_size, progress_callback=update_progress
                )

            progress_bar.progress(100, text="Pipeline completed and database fully synced!")
            status_text.empty()

            st.success(
                f"🎉 **Silver database repopulated and synced successfully!**\n\n"
                f"- **Total Enriched Transactions**: {res_repop['silver_count']:,}\n"
                f"- **Auto-Matched Merchants**: {res_repop['matched_count']}\n"
                f"- **Gemini AI Categorized**: {res_repop['ai_count']}\n"
            )
            st.rerun()

    st.divider()

    # -------------------------------------------------------------
    # Section: Interactive Review & Editor for Silver Layer
    # -------------------------------------------------------------
    st.markdown("#### 🏷️ Silver Layer Data Viewer & Category Editor")
    st.caption(
        "Inspect enriched transactions published in Silver, review motivation, and edit categories directly."
    )

    df_silver_current = load_silver_data()
    if not df_silver_current.empty:
        col_f1, col_f2 = st.columns([2, 1])
        with col_f1:
            search_query = st.text_input("🔍 Search merchant in Silver:", value="")
        with col_f2:
            cat_filter = st.selectbox(
                "Filter by category:", options=["All"] + list(CATEGORY_CONFIG.keys())
            )

        df_display = df_silver_current.copy()
        if search_query.strip():
            df_display = df_display[
                df_display["id"].str.contains(search_query.strip(), case=False, na=False)
            ]
        if cat_filter != "All":
            df_display = df_display[df_display["category"] == cat_filter]

        # Prioritize unclassified / not_found items first, then sort by merchant name (A-Z), then latest dates
        df_display["_is_not_found"] = (
            df_display["category"]
            .fillna("")
            .astype(str)
            .str.lower()
            .isin(["not_found", "pending", "none", ""])
        )
        df_display = (
            df_display.sort_values(
                by=["_is_not_found", "id", "date"], ascending=[False, True, False]
            )
            .drop(columns=["_is_not_found"])
            .reset_index(drop=True)
        )

        df_edited = st.data_editor(
            df_display[
                [
                    "date",
                    "date_buy",
                    "id",
                    "source_debt",
                    "cost",
                    "installment",
                    "total_installments",
                    "category",
                    "motivation",
                    "categorized_by",
                ]
            ],
            column_config={
                "date": st.column_config.DateColumn("Invoice Date", format="YYYY-MM-DD"),
                "date_buy": st.column_config.DateColumn("Purchase Date", format="YYYY-MM-DD"),
                "id": st.column_config.TextColumn("Merchant ID"),
                "source_debt": st.column_config.TextColumn("Cardholder"),
                "cost": st.column_config.NumberColumn("Amount (R$)", format="R$ %.2f"),
                "installment": st.column_config.NumberColumn("Installment"),
                "total_installments": st.column_config.NumberColumn("Total Installments"),
                "category": st.column_config.SelectboxColumn(
                    "Category",
                    options=list(CATEGORY_CONFIG.keys()),
                    required=True,
                ),
                "motivation": st.column_config.TextColumn("Motivation / Reason"),
                "categorized_by": st.column_config.TextColumn("Source", disabled=True),
            },
            use_container_width=True,
            num_rows="dynamic",
            key="editor_silver_live",
        )

        if st.button("💾 Save Manual Adjustments to Silver Layer", type="secondary"):
            with st.spinner("Persisting edits to Silver database..."):
                if engine_silver is not None:
                    save_dataframe_replace(df_edited, engine_silver, MYSQL_DB_SILVER)
                clear_caches()
                st.success("Silver layer records successfully updated!")
                st.rerun()
    else:
        st.info(
            "The Silver layer is currently empty. Click the trigger button above to categorize and populate from Bronze."
        )
