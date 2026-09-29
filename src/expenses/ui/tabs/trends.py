import pandas as pd
import streamlit as st

from src.expenses.analytics import (
    get_category_momentum,
    get_period_over_period_comparison,
    get_spending_trend,
    get_year_over_year_comparison,
)
from src.expenses.config import format_currency_br
from src.expenses.ui.figures import (
    build_period_comparison_figure,
    build_trend_figure,
    build_yoy_figure,
)

_DIRECTION = {"up": "Rising", "down": "Falling", "stable": "Stable"}
_MOMENTUM_ICONS = {"rising": "▲ Rising", "falling": "▼ Falling", "stable": "→ Stable"}
_VS_PREVIOUS = "vs previous period"
_VS_LAST_YEAR = "vs last year"


def _render_kpis(trend: dict, pop: dict) -> None:
    k1, k2, k3, k4 = st.columns(4)
    if trend["has_data"]:
        k1.metric(
            "Trend",
            _DIRECTION[trend["direction"]],
            help="Linear regression over the selected invoices.",
            border=True,
        )
        k2.metric("3-month average", format_currency_br(trend["current_avg"]), border=True)
        k3.metric(
            "Next month (projected)",
            format_currency_br(trend["projected_next"]),
            help="Extrapolated from the trend line.",
            border=True,
        )
    else:
        k1.metric("Trend", "—", help="Needs at least two months of data.", border=True)
        k2.metric("3-month average", "—", border=True)
        k3.metric("Next month (projected)", "—", border=True)

    if pop["has_data"]:
        cur, prev = pop["current_months"], pop["previous_months"]
        k4.metric(
            "Selected period",
            format_currency_br(pop["current_total"]),
            delta=f"{pop['delta_pct']:+.1f}% vs previous",
            delta_color="inverse",
            help=f"{cur[0]} → {cur[-1]} compared with {prev[0]} → {prev[-1]}.",
            border=True,
        )
    else:
        k4.metric("Selected period", "—", help="No earlier period to compare.", border=True)


def _render_comparison(pop: dict, yoy: pd.DataFrame) -> None:
    options = [_VS_PREVIOUS] + ([_VS_LAST_YEAR] if not yoy.empty else [])
    title_col, control_col = st.columns([3, 2])
    title_col.markdown("##### Comparison")
    mode = control_col.segmented_control(
        "Compare",
        options,
        default=_VS_PREVIOUS,
        required=True,
        key="tr_compare_mode",
        label_visibility="collapsed",
    )

    if mode == _VS_LAST_YEAR:
        cur_year = int(yoy["current_year"].iloc[0])
        prev_year = int(yoy["previous_year"].iloc[0])
        st.caption(f"Same months, {prev_year} vs {cur_year}.")
        st.plotly_chart(build_yoy_figure(yoy), width="stretch")
        return

    if not pop["has_data"]:
        st.caption("Not enough history before the selected period to compare.")
        return
    st.caption("Top 10 categories: selected invoices vs the same number of months before them.")
    fig = build_period_comparison_figure(pop)
    if fig is not None:
        st.plotly_chart(fig, width="stretch")


def render_trends_tab(df_filtered: pd.DataFrame, df_full: pd.DataFrame):
    """Trends: is spending going up or down, and against what?"""
    if df_filtered.empty:
        st.info("No transactions found with the selected filters.")
        return

    df_expenses = df_filtered[~df_filtered["is_payment"]].copy()
    trend = get_spending_trend(df_expenses, group_col="year_month")
    selected_months = sorted(df_filtered["year_month"].dropna().unique().tolist())
    pop = get_period_over_period_comparison(df_full, selected_months)
    yoy = get_year_over_year_comparison(df_full)

    st.caption("Whether your spending is rising or falling, and how it compares.")
    _render_kpis(trend, pop)

    with st.container(border=True):
        st.markdown("##### Net spending and 3-month average")
        fig = build_trend_figure(trend["moving_avg_df"]) if trend["has_data"] else None
        if fig is not None:
            st.plotly_chart(fig, width="stretch")
        else:
            st.caption("Needs at least two months of data.")

    with st.container(border=True):
        _render_comparison(pop, yoy)

    momentum = get_category_momentum(df_full, window=3)
    with st.expander("Category momentum (last 3 months)"):
        if momentum.empty:
            st.caption("Needs 3+ months of data per category.")
        else:
            st.dataframe(
                pd.DataFrame(
                    {
                        "Category": momentum["category_label"],
                        "Trend": momentum["direction"].map(_MOMENTUM_ICONS),
                        "Last month": momentum["last_month_value"].astype(float),
                        "3-month change": momentum["pct_change_over_window"] / 100.0,
                    }
                ),
                column_config={
                    "Last month": st.column_config.NumberColumn(format="R$ %.2f"),
                    "3-month change": st.column_config.NumberColumn(format="percent"),
                },
                width="stretch",
                hide_index=True,
            )
