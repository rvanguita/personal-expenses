import io
from datetime import UTC, datetime

import pandas as pd
import streamlit as st

from src.expenses.analytics import (
    get_future_installments_details,
    get_future_installments_projection,
    get_next_month_commitment_metrics,
)
from src.expenses.config import REFERENCE_BUDGET_LIMIT, format_currency_br
from src.expenses.ui.figures import build_budget_vs_limit_figure, build_future_by_category_figure
from src.expenses.ui.styles import section

_MONEY = st.column_config.NumberColumn(format="R$ %.2f")
_DATE = st.column_config.DateColumn(format="YYYY-MM-DD")
_VS_LIMIT = "vs limit"
_BY_CATEGORY = "by category"


def _installments_label(installment, total) -> str:
    return f"{int(installment)}/{int(total)}" if total > 1 else "Single payment"


def _invoice_totals(df_expenses: pd.DataFrame) -> pd.DataFrame:
    summary = (
        df_expenses.groupby(["year_month", "date"])
        .agg(
            count=("cost", "count"),
            gross=("cost", lambda s: s[s > 0].sum()),
            refunds=("cost", lambda s: s[s < 0].sum()),
            net=("cost", "sum"),
        )
        .reset_index()
        .sort_values(by="date", ascending=False)
    )
    return pd.DataFrame(
        {
            "Invoice": summary["year_month"],
            "Invoice date": pd.to_datetime(summary["date"]),
            "Transactions": summary["count"].astype(int),
            "Gross": summary["gross"].astype(float),
            "Refunds": summary["refunds"].astype(float),
            "Net total": summary["net"].astype(float),
        }
    )


def _render_commitments(df_full: pd.DataFrame) -> None:
    section("Installment commitments", "Budget already locked into future installments.")
    limit_col, _ = st.columns([1, 3])
    ref_limit = limit_col.number_input(
        "Monthly budget limit (R$)",
        value=float(REFERENCE_BUDGET_LIMIT),
        step=500.0,
        min_value=100.0,
        format="%.0f",
        help="Defaults to REFERENCE_BUDGET_LIMIT from .env.",
    )

    metrics = get_next_month_commitment_metrics(df_full, reference_limit=ref_limit)
    projection = get_future_installments_projection(df_full)
    details = get_future_installments_details(df_full)
    if not metrics["has_data"] or projection.empty:
        st.info("No active installment purchases found.")
        return

    over = metrics["is_over_limit"]
    k1, k2, k3 = st.columns(3)
    k1.metric(
        f"Next month ({metrics['next_month']})",
        format_currency_br(metrics["next_month_cost"]),
        delta=(
            f"+{format_currency_br(metrics['diff_from_limit'])} over limit"
            if over
            else f"{format_currency_br(abs(metrics['diff_from_limit']))} left"
        ),
        delta_color="inverse" if over else "normal",
        help=f"{metrics['num_installments']} installments billed next month.",
        border=True,
    )
    k2.metric("Share of limit", f"{metrics['pct_of_limit']:.1f}%", border=True)
    k3.metric(
        "Total future installments",
        format_currency_br(metrics["total_future_debt"]),
        delta=f"over {metrics['months_count']} months",
        delta_color="off",
        delta_arrow="off",
        help=f"Last installment billed in {metrics['max_future_month']}.",
        border=True,
    )

    with st.container(border=True):
        title_col, control_col = st.columns([3, 2])
        title_col.markdown("##### Committed per month")
        view = control_col.segmented_control(
            "View",
            [_VS_LIMIT, _BY_CATEGORY],
            default=_VS_LIMIT,
            required=True,
            key="rp_commit_view",
            label_visibility="collapsed",
        )
        fig = (
            build_future_by_category_figure(details)
            if view == _BY_CATEGORY
            else build_budget_vs_limit_figure(projection, ref_limit)
        )
        if fig is not None:
            st.plotly_chart(fig, width="stretch")

    if not details.empty:
        with st.expander("Upcoming installments by purchase"):
            st.dataframe(
                pd.DataFrame(
                    {
                        "Billing month": details["future_month"],
                        "Merchant": details["id"],
                        "Category": details["category_label"],
                        "Purchase date": pd.to_datetime(details["date_buy"]),
                        "Installment": details["installment_display"],
                        "Amount": details["cost"].astype(float),
                    }
                ),
                column_config={"Purchase date": _DATE, "Amount": _MONEY},
                width="stretch",
                hide_index=True,
            )


def _render_export(df_filtered: pd.DataFrame, df_expenses: pd.DataFrame) -> None:
    section("Data", "Tables for the selected filters.")
    with st.expander("Invoice totals"):
        st.dataframe(
            _invoice_totals(df_expenses),
            column_config={
                "Invoice date": _DATE,
                "Gross": _MONEY,
                "Refunds": _MONEY,
                "Net total": _MONEY,
            },
            width="stretch",
            hide_index=True,
        )

    with st.expander(f"All transactions ({len(df_filtered):,})"):
        st.dataframe(
            pd.DataFrame(
                {
                    "Invoice date": pd.to_datetime(df_filtered["date"]),
                    "Purchase date": pd.to_datetime(df_filtered["date_buy"]),
                    "Merchant": df_filtered["id"],
                    "Category": df_filtered["category_label"],
                    "Amount": df_filtered["cost"].astype(float),
                    "Installments": [
                        _installments_label(i, t)
                        for i, t in zip(
                            df_filtered["installment"],
                            df_filtered["total_installments"],
                            strict=True,
                        )
                    ],
                }
            ),
            column_config={"Invoice date": _DATE, "Purchase date": _DATE, "Amount": _MONEY},
            width="stretch",
            hide_index=True,
        )

    csv_buffer = io.StringIO()
    df_filtered.to_csv(csv_buffer, index=False, sep=";", encoding="utf-8-sig")
    st.download_button(
        label="Download CSV",
        data=csv_buffer.getvalue(),
        file_name=f"expenses_report_{datetime.now(tz=UTC).strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )


def render_reports_tab(df_filtered: pd.DataFrame, df_full: pd.DataFrame):
    """Reports: future installment commitments and data export."""
    if df_filtered.empty:
        st.info("No data selected to generate report.")
        return

    df_expenses = df_filtered[~df_filtered["is_payment"]].copy()
    _render_commitments(df_full)
    _render_export(df_filtered, df_expenses)
