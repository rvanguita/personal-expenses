import pandas as pd
import streamlit as st

from expenses.analytics import (
    calculate_kpis,
    get_moving_average,
    get_next_month_commitment_metrics,
)
from expenses.config import REFERENCE_BUDGET_LIMIT, format_currency_br
from expenses_streamlit.figures import (
    build_category_distribution_figure,
    build_top_merchants_figure,
    build_trend_figure,
)
from expenses_streamlit.insights import attention_insights
from expenses_streamlit.styles import render_attention


def _render_kpis(kpis: dict, df_full: pd.DataFrame) -> None:
    commitment = get_next_month_commitment_metrics(df_full, reference_limit=REFERENCE_BUDGET_LIMIT)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Net spent",
        format_currency_br(kpis["total_spent"]),
        help=(
            f"Gross {format_currency_br(kpis['gross_spent'])} · refunds "
            f"{format_currency_br(kpis['total_refunds'])} · {kpis['total_tx']:,} transactions"
        ),
        border=True,
    )
    k2.metric(
        "Monthly average",
        format_currency_br(kpis["avg_monthly_spent"]),
        help=f"Average net total across {kpis['num_months']} selected invoice(s).",
        border=True,
    )
    k3.metric(
        "Latest invoice",
        format_currency_br(kpis["latest_m_val"]),
        delta=f"{kpis['mom_delta_pct']:+.1f}% vs previous",
        delta_color="inverse",
        help="Latest invoice compared with the one before it.",
        border=True,
    )
    if commitment["has_data"]:
        k4.metric(
            f"Installments {commitment['next_month']}",
            format_currency_br(commitment["next_month_cost"]),
            delta=f"{commitment['pct_of_limit']:.0f}% of limit",
            delta_color="off",
            delta_arrow="off",
            help=(
                f"{commitment['num_installments']} installments already due next month, against "
                f"the {format_currency_br(REFERENCE_BUDGET_LIMIT)} reference limit."
            ),
            border=True,
        )
    else:
        k4.metric("Next month installments", format_currency_br(0.0), border=True)


def render_dashboard_tab(df_filtered: pd.DataFrame, df_full: pd.DataFrame):
    """Overview: how much was spent in the selected period and where it went."""
    if df_filtered.empty:
        st.info("No transactions found with the selected filters.")
        return

    df_expenses = df_filtered[~df_filtered["is_payment"]].copy()
    kpis = calculate_kpis(df_filtered, df_full)

    _render_kpis(kpis, df_full)
    render_attention(
        attention_insights(kpis, df_expenses, df_full, reference_limit=REFERENCE_BUDGET_LIMIT)
    )

    with st.container(border=True):
        st.markdown("##### Monthly spending")
        st.caption("Net total per invoice with its 3-month moving average.")
        fig = build_trend_figure(get_moving_average(df_expenses, window=3))
        if fig is not None:
            st.plotly_chart(fig, width="stretch")
        else:
            st.caption("Needs at least two months of data.")

    left, right = st.columns(2)
    with left, st.container(border=True):
        st.markdown("##### By category")
        fig = build_category_distribution_figure(df_expenses, height=400)
        if fig is not None:
            st.plotly_chart(fig, width="stretch")
    with right, st.container(border=True):
        st.markdown("##### Top 10 merchants")
        fig = build_top_merchants_figure(df_expenses, top_n=10, height=400)
        if fig is not None:
            st.plotly_chart(fig, width="stretch")
