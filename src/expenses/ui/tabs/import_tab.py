from datetime import UTC, datetime

import pandas as pd
import streamlit as st

from src.expenses.config import format_currency_br
from src.expenses.database import ingest_raw_bronze
from src.expenses.parser import parse_raw_csv, transform_raw_to_bronze


def render_import_tab(engine=None):
    """Renders the Batch Invoice Ingestion tab (Raw & Bronze layer persistence)."""
    st.markdown("### 📥 Invoice Ingestion (Raw & Bronze Layers)")
    st.caption(
        "Upload one or multiple credit card CSV invoices at once. Ingested files are stored identically in the **Raw** database "
        "and transformed with standardized schema into the **Bronze** database. Categorization is performed in the dedicated **🏷️ AI Categorization** tab."
    )

    col_u1, col_u2 = st.columns([3, 2])
    with col_u1:
        uploaded_files = st.file_uploader(
            "Select one or multiple invoice CSV files (delimited by ; or ,):",
            type=["csv"],
            accept_multiple_files=True,
            help="You can drag and drop multiple CSV files at once.",
        )
    with col_u2:
        manual_date = st.date_input(
            "Fallback Invoice Due Date (if not detected in filename):",
            value=datetime.now(tz=UTC).date(),
            help="Used only if an uploaded file's name does not contain YYYY-MM-DD.",
        )

    if uploaded_files:
        st.write("")
        st.markdown(f"#### 📑 Uploaded Files Overview ({len(uploaded_files)} file(s) selected)")

        parsed_files = []
        all_raw_dfs = []
        all_bronze_dfs = []

        # Parse all uploaded files
        for uploaded_file in uploaded_files:
            df_raw = parse_raw_csv(uploaded_file, fallback_date=manual_date)
            df_bronze = transform_raw_to_bronze(df_raw)

            if not df_bronze.empty:
                inv_date = pd.to_datetime(df_bronze["date"].iloc[0]).strftime("%d/%m/%Y")
                total_val = float(df_bronze["cost"].sum())
                gross_val = float(df_bronze[df_bronze["cost"] > 0]["cost"].sum())
                tx_count = len(df_bronze)

                parsed_files.append(
                    {
                        "filename": uploaded_file.name,
                        "invoice_date": inv_date,
                        "transactions": tx_count,
                        "gross_spent": gross_val,
                        "net_total": total_val,
                        "df_raw": df_raw,
                        "df_bronze": df_bronze,
                    }
                )
                all_raw_dfs.append(df_raw)
                all_bronze_dfs.append(df_bronze)

        if parsed_files:
            total_all_tx = sum(p["transactions"] for p in parsed_files)
            total_all_gross = sum(p["gross_spent"] for p in parsed_files)
            total_all_net = sum(p["net_total"] for p in parsed_files)

            # Global batch KPI metrics
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("📁 Selected Files", f"{len(parsed_files):,}")
            m2.metric("🧾 Total Transactions", f"{total_all_tx:,}")
            m3.metric("💳 Gross Purchases", format_currency_br(total_all_gross))
            m4.metric("💰 Net Total", format_currency_br(total_all_net))

            # Batch Summary Table
            df_summary_table = pd.DataFrame(
                [
                    {
                        "File Name": p["filename"],
                        "Invoice Date": p["invoice_date"],
                        "Transactions": p["transactions"],
                        "Gross Purchases": p["gross_spent"],
                        "Net Invoice Total": p["net_total"],
                        "Status": "✅ Ready to Ingest",
                    }
                    for p in parsed_files
                ]
            )
            st.dataframe(
                df_summary_table,
                column_config={
                    "File Name": st.column_config.TextColumn("File Name"),
                    "Invoice Date": st.column_config.TextColumn("Invoice Date"),
                    "Transactions": st.column_config.NumberColumn("Transactions", format="%d"),
                    "Gross Purchases": st.column_config.NumberColumn(
                        "Gross Purchases", format="R$ %.2f"
                    ),
                    "Net Invoice Total": st.column_config.NumberColumn(
                        "Net Invoice Total", format="R$ %.2f"
                    ),
                    "Status": st.column_config.TextColumn("Status"),
                },
                use_container_width=True,
                hide_index=True,
            )

            # Preview Expander for Data Inspection
            with st.expander("🔍 **Inspect Raw & Bronze Previews**", expanded=False):
                file_names = [p["filename"] for p in parsed_files]
                selected_preview_file = st.selectbox(
                    "Select file to preview:",
                    options=file_names,
                    key="preview_file_select",
                )
                chosen_parsed = next(
                    p for p in parsed_files if p["filename"] == selected_preview_file
                )

                col_prev1, col_prev2 = st.columns(2)
                with col_prev1:
                    st.markdown("##### 🧱 Raw Layer Preview")
                    st.dataframe(
                        chosen_parsed["df_raw"].head(5), use_container_width=True, hide_index=True
                    )

                with col_prev2:
                    st.markdown("##### 🥉 Bronze Layer Preview")
                    df_bronze_disp = chosen_parsed["df_bronze"].head(5).copy()
                    df_bronze_disp["date"] = pd.to_datetime(df_bronze_disp["date"])
                    df_bronze_disp["date_buy"] = pd.to_datetime(df_bronze_disp["date_buy"])
                    df_bronze_disp["cost"] = df_bronze_disp["cost"].astype(float)
                    st.dataframe(
                        df_bronze_disp,
                        column_config={
                            "date": st.column_config.DateColumn(
                                "Invoice Date", format="YYYY-MM-DD"
                            ),
                            "date_buy": st.column_config.DateColumn(
                                "Purchase Date", format="YYYY-MM-DD"
                            ),
                            "id": st.column_config.TextColumn("Merchant / ID"),
                            "cost": st.column_config.NumberColumn("Amount", format="R$ %.2f"),
                            "installment": st.column_config.NumberColumn("Installment"),
                            "total_installments": st.column_config.NumberColumn(
                                "Total Installments"
                            ),
                            "source_debt": st.column_config.TextColumn("Cardholder"),
                            "source_file": st.column_config.TextColumn("Source File"),
                        },
                        use_container_width=True,
                        hide_index=True,
                    )

            st.write("")

            # Action Button to Ingest all files into Raw and Bronze
            btn_label = (
                f"💾 Ingest All {len(parsed_files)} Invoices into Raw & Bronze Layers"
                if len(parsed_files) > 1
                else "💾 Ingest Invoice into Raw & Bronze Layers"
            )

            if st.button(btn_label, type="primary", use_container_width=True):
                progress_bar = st.progress(0, text="Starting batch ingestion...")

                def _progress(done, total, filename):
                    progress_bar.progress(
                        int(done / max(total, 1) * 100),
                        text=f"Processing file {done}/{total}: {filename}...",
                    )

                res = ingest_raw_bronze(parsed_files, progress=_progress)
                progress_bar.progress(100, text="Batch ingestion completed!")

                st.success(
                    f"🎉 Successfully ingested **{len(parsed_files)}** invoice file(s)!\n\n"
                    f"- **Raw Layer**: Added **{res['raw_inserted']:,}** lines.\n"
                    f"- **Bronze Layer**: Added **{res['bronze_inserted']:,}** new transactions "
                    f"(Skipped {res['bronze_skipped']} duplicates).\n\n"
                    f"👉 Head over to the **🏷️ AI Categorization & Matching** tab to categorize "
                    f"new transactions."
                )
                if st.button("🔄 Refresh Data View"):
                    st.rerun()
