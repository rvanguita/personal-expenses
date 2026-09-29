import io
from datetime import UTC, datetime

import pandas as pd
import streamlit as st

from src.expenses.analytics import (
    get_future_installments_details,
    get_future_installments_projection,
    get_next_month_commitment_metrics,
)
from src.expenses.config import format_currency_br, format_currency_md
from src.expenses.ui.figures import build_budget_vs_limit_figure, build_future_by_category_figure
from src.expenses.ui.insights import executive_summary_insight
from src.expenses.ui.styles import render_insight_card


def render_reports_tab(df_filtered: pd.DataFrame, df_full: pd.DataFrame):
    """Renders executive reports, future installment projections, and CSV export."""
    if df_filtered.empty:
        st.info("No data selected to generate report.")
        return

    st.markdown("### 📑 Executive Report & Spending Diagnosis")

    # Automatic spending diagnosis
    df_exp = (
        df_filtered[~df_filtered["is_payment"]].copy()
        if "is_payment" in df_filtered.columns
        else df_filtered[
            ~df_filtered["id"].str.contains(
                r"PAGAMENTO|PAGTO|PAYMENT|PAGAMENTOS VALIDOS", case=False, regex=True, na=False
            )
        ].copy()
    )
    summary = executive_summary_insight(df_exp)
    render_insight_card(summary.icon, summary.title, summary.message, severity=summary.severity)

    # ----------------------------------------------------
    # Future Installments & Budget Lock Forecast
    # ----------------------------------------------------
    st.markdown("#### 🔮 Future Installments & Budget Lock Forecast")
    st.caption(
        "Analyze how much of your future income/budget is already locked into credit card installments for upcoming months, compared against a reference limit (e.g. 5k)."
    )

    col_ctrl1, col_ctrl2 = st.columns([1, 2])
    with col_ctrl1:
        ref_limit = st.number_input(
            "🎯 Reference Budget Limit (R$):",
            value=5000.0,
            step=500.0,
            min_value=100.0,
            help="Reference threshold to monitor committed future expenses against your monthly budget.",
        )

    metrics_next = get_next_month_commitment_metrics(df_full, reference_limit=ref_limit)
    df_projection = get_future_installments_projection(df_full)
    df_details = get_future_installments_details(df_full)

    if metrics_next["has_data"] and not df_projection.empty:
        # Forecast KPI Cards
        with st.container(border=True):
            k1, k2, k3, k4 = st.columns(4)

            next_diff_label = (
                f"+{format_currency_br(metrics_next['diff_from_limit'])} Over Limit"
                if metrics_next["is_over_limit"]
                else f"{format_currency_br(abs(metrics_next['diff_from_limit']))} Remaining"
            )
            delta_color = "inverse" if metrics_next["is_over_limit"] else "normal"

            k1.metric(
                f"🔒 Next Month ({metrics_next['next_month']})",
                format_currency_br(metrics_next["next_month_cost"]),
                delta=next_diff_label,
                delta_color=delta_color,
            )
            k1.caption(f"{metrics_next['num_installments']} active installments billed")

            k2.metric(
                "🎯 % of Reference Limit",
                f"{metrics_next['pct_of_limit']:.1f}%",
                delta="Over Limit!" if metrics_next["is_over_limit"] else "Within Safe Budget",
                delta_color=delta_color,
            )
            k2.caption(f"Ref Limit: {format_currency_md(ref_limit)}")

            k3.metric(
                "💳 Total Future Installments Debt",
                format_currency_br(metrics_next["total_future_debt"]),
            )
            k3.caption("Sum of all remaining future installments")

            k4.metric(
                "🗓️ Forecast Horizon",
                f"{metrics_next['months_count']} months",
            )
            k4.caption(f"Until {metrics_next['max_future_month']}")

        st.write("")

        # ------------------------------------------------
        # Dual Charts: Total vs Reference Limit + Category Breakdown
        # ------------------------------------------------
        col_c1, col_c2 = st.columns(2)

        with col_c1:
            with st.container(border=True):
                st.markdown("##### 📊 Monthly Locked Budget vs Reference Line")
                fig_bar_ref = build_budget_vs_limit_figure(df_projection, ref_limit)
                st.plotly_chart(fig_bar_ref, use_container_width=True)

        with col_c2:
            with st.container(border=True):
                st.markdown("##### 🏷️ Future Commitments by Category")
                fig_cat_future = build_future_by_category_figure(df_details)
                if fig_cat_future is not None:
                    st.plotly_chart(fig_cat_future, use_container_width=True)

        # Summary Dataframe & Detailed Breakdown
        with st.expander(
            "🔍 View Detailed List of Upcoming Installments by Purchase", expanded=False
        ):
            if not df_details.empty:
                df_display_details = df_details.copy()
                df_display_details["Purchase Date"] = pd.to_datetime(df_display_details["date_buy"])
                df_display_details["Cost"] = df_display_details["cost"].astype(float)
                df_display_details = df_display_details.rename(
                    columns={
                        "future_month": "Billing Month",
                        "id": "Merchant",
                        "installment_display": "Installment",
                        "category_label": "Category",
                    }
                )[["Billing Month", "Merchant", "Category", "Purchase Date", "Installment", "Cost"]]
                st.dataframe(
                    df_display_details,
                    column_config={
                        "Billing Month": st.column_config.TextColumn("Billing Month"),
                        "Merchant": st.column_config.TextColumn("Merchant"),
                        "Category": st.column_config.TextColumn("Category"),
                        "Purchase Date": st.column_config.DateColumn(
                            "Purchase Date", format="YYYY-MM-DD"
                        ),
                        "Installment": st.column_config.TextColumn("Installment"),
                        "Cost": st.column_config.NumberColumn("Cost", format="R$ %.2f"),
                    },
                    use_container_width=True,
                    hide_index=True,
                )

    else:
        st.info("No active installment purchases found in the database.")

    st.divider()

    # ------------------------------------
    # Complete Data Table & CSV Export
    # ------------------------------------
    st.markdown("#### 📑 Complete Data Table (Filtered)")
    df_export = df_filtered.copy()
    df_export_display = df_export[
        ["date", "date_buy", "id", "cost", "installment", "total_installments", "category_label"]
    ].copy()
    df_export_display["Invoice Date"] = pd.to_datetime(df_export_display["date"])
    df_export_display["Purchase Date"] = pd.to_datetime(df_export_display["date_buy"])
    df_export_display["Merchant"] = df_export_display["id"]
    df_export_display["Category"] = df_export_display["category_label"]
    df_export_display["Amount"] = df_export_display["cost"].astype(float)
    df_export_display["Installments"] = df_export_display.apply(
        lambda r: (
            f"{int(r['installment'])}/{int(r['total_installments'])}"
            if r["total_installments"] > 1
            else "Single Payment"
        ),
        axis=1,
    )

    st.dataframe(
        df_export_display[
            ["Invoice Date", "Purchase Date", "Merchant", "Category", "Amount", "Installments"]
        ],
        column_config={
            "Invoice Date": st.column_config.DateColumn("Invoice Date", format="YYYY-MM-DD"),
            "Purchase Date": st.column_config.DateColumn("Purchase Date", format="YYYY-MM-DD"),
            "Merchant": st.column_config.TextColumn("Merchant"),
            "Category": st.column_config.TextColumn("Category"),
            "Amount": st.column_config.NumberColumn("Amount", format="R$ %.2f"),
            "Installments": st.column_config.TextColumn("Installments"),
        },
        use_container_width=True,
        hide_index=True,
    )

    # CSV Download Button
    csv_buffer = io.StringIO()
    df_export.to_csv(csv_buffer, index=False, sep=";", encoding="utf-8-sig")
    st.download_button(
        label="📥 Download Report as CSV",
        data=csv_buffer.getvalue(),
        file_name=f"expenses_report_{datetime.now(tz=UTC).strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )
