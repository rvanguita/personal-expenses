import pandas as pd
import streamlit as st

from src.expenses.analytics import calculate_kpis, get_financial_health_score
from src.expenses.config import REFERENCE_BUDGET_LIMIT, format_currency_br
from src.expenses.ui.figures import (
    CHART_STYLE_LINES,
    CHART_STYLE_STACKED,
    build_category_distribution_figure,
    build_monthly_evolution_figure,
    build_top_merchants_figure,
)
from src.expenses.ui.insights import HEALTH_FACTOR_LABELS, attention_insights
from src.expenses.ui.styles import render_attention, section

_DATE_BASIS = {"Invoice date": "year_month", "Purchase date": "buy_year_month"}
_CHART_STYLES = {"Stacked": CHART_STYLE_STACKED, "Lines": CHART_STYLE_LINES}


def _render_kpis(kpis: dict, df_full: pd.DataFrame) -> None:
    health = get_financial_health_score(df_full)

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
        help="Latest selected invoice compared with the one before it.",
        border=True,
    )
    if health["has_data"]:
        factor = health["top_factor"]
        k4.metric(
            "Financial health",
            f"{health['score']}/100",
            delta=health["rating"],
            delta_color="off",
            delta_arrow="off",
            help=(
                "Composite of installment burden, unusual purchases, upcoming budget and "
                f"volatility (full history). Weakest: {HEALTH_FACTOR_LABELS.get(factor, factor)}."
            ),
            border=True,
        )
    else:
        k4.metric(
            "Transactions",
            f"{kpis['total_tx']:,}",
            help=f"Average ticket {format_currency_br(kpis['avg_tx'])}.",
            border=True,
        )


def render_dashboard_tab(df_filtered: pd.DataFrame, df_full: pd.DataFrame):
    """Overview: how much was spent in the selected period and where it went."""
    if df_filtered.empty:
        st.info("No transactions found with the selected filters.")
        return

    df_expenses = df_filtered[~df_filtered["is_payment"]].copy()
    kpis = calculate_kpis(df_filtered, df_full)

    st.caption("How much you spent in the selected period and where it went.")
    _render_kpis(kpis, df_full)

    section("Needs attention")
    render_attention(
        attention_insights(kpis, df_expenses, df_full, reference_limit=REFERENCE_BUDGET_LIMIT)
    )

    with st.container(border=True):
        title_col, options_col = st.columns([5, 1])
        title_col.markdown("##### Monthly spending by category")
        with options_col.popover("Options", width="stretch"):
            basis = st.radio("Group by", list(_DATE_BASIS), key="ov_date_basis")
            style = st.radio("View", list(_CHART_STYLES), key="ov_chart_style")
        fig = build_monthly_evolution_figure(
            df_expenses, group_col=_DATE_BASIS[basis], chart_style=_CHART_STYLES[style]
        )
        if fig is not None:
            st.plotly_chart(fig, width="stretch")

    left, right = st.columns(2)
    with left, st.container(border=True):
        st.markdown("##### Spending by category")
        fig = build_category_distribution_figure(df_expenses, height=400)
        if fig is not None:
            st.plotly_chart(fig, width="stretch")
    with right, st.container(border=True):
        st.markdown("##### Top 10 merchants")
        fig = build_top_merchants_figure(df_expenses, top_n=10, height=400)
        if fig is not None:
            st.plotly_chart(fig, width="stretch")
