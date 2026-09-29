import pandas as pd
import streamlit as st

from src.expenses.analytics import (
    get_category_momentum,
    get_merchant_frequency_change,
    get_period_over_period_comparison,
    get_recurring_merchants,
    get_spending_anomalies,
    get_spending_trend,
    get_year_over_year_comparison,
)
from src.expenses.config import (
    ANOMALY_MIN_CATEGORY_TX,
    ANOMALY_Z_THRESHOLD,
    RECURRING_MAX_CV,
    RECURRING_MIN_MONTHS,
    format_currency_br,
)
from src.expenses.ui.figures import (
    build_period_comparison_figure,
    build_trend_figure,
    build_yoy_figure,
)
from src.expenses.ui.insights import (
    anomalies_insight,
    frequency_change_insight,
    top_momentum_insight,
)
from src.expenses.ui.styles import render_insight_card

_MOMENTUM_ICONS = {"rising": "▲", "falling": "▼", "stable": "→"}


def _render(insight) -> None:
    render_insight_card(insight.icon, insight.title, insight.message, severity=insight.severity)


def render_trends_tab(df_filtered: pd.DataFrame, df_full: pd.DataFrame):
    """Renders trend/forecast, period-over-period, year-over-year, category momentum, recurring
    subscriptions, merchant frequency change, and anomaly analysis."""
    if df_filtered.empty:
        st.info("No transactions found with the selected filters.")
        return

    df_expenses = (
        df_filtered[~df_filtered["is_payment"]].copy()
        if "is_payment" in df_filtered.columns
        else df_filtered.copy()
    )

    st.markdown("### 📈 Trends, Comparisons & Anomaly Detection")

    # ------------------------------------
    # Trend & Forecast
    # ------------------------------------
    st.markdown("#### 🔮 Spending Trend & Next Month Forecast")
    trend = get_spending_trend(df_expenses, group_col="year_month")

    if trend["has_data"]:
        with st.container(border=True):
            t1, t2, t3 = st.columns(3)

            direction_label = {
                "up": "📈 Rising",
                "down": "📉 Falling",
                "stable": "⚖️ Stable",
            }[trend["direction"]]

            t1.metric("Trend Direction", direction_label)
            t1.caption("Based on a linear regression over the visible period")

            t2.metric("3-Month Moving Average", format_currency_br(trend["current_avg"]))
            t2.caption("Smoothed recent spending level")

            t3.metric("Projected Next Month", format_currency_br(trend["projected_next"]))
            t3.caption("Simple trend-line projection")

            fig_trend = build_trend_figure(trend["moving_avg_df"])
            if fig_trend is not None:
                st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("Not enough monthly data yet to compute a spending trend.")

    st.write("")

    # ------------------------------------
    # Period-over-Period Comparison
    # ------------------------------------
    st.markdown("#### ⏮️ Period-over-Period Comparison")
    st.caption(
        "Compares the currently selected invoices against the immediately preceding period of equal length."
    )

    selected_months = sorted(df_filtered["year_month"].dropna().unique().tolist())
    pop = get_period_over_period_comparison(df_full, selected_months)

    if pop["has_data"]:
        with st.container(border=True):
            p1, p2, p3 = st.columns(3)
            p1.metric(
                f"Current Period ({len(pop['current_months'])} mo.)",
                format_currency_br(pop["current_total"]),
            )
            p1.caption(f"{pop['current_months'][0]} → {pop['current_months'][-1]}")

            p2.metric(
                f"Previous Period ({len(pop['previous_months'])} mo.)",
                format_currency_br(pop["previous_total"]),
            )
            p2.caption(f"{pop['previous_months'][0]} → {pop['previous_months'][-1]}")

            p3.metric(
                "Variation",
                format_currency_br(pop["delta"]),
                delta=f"{pop['delta_pct']:+.1f}%",
                delta_color="inverse",
            )
            p3.caption("Current vs previous period")

            fig_pop = build_period_comparison_figure(pop)
            if fig_pop is not None:
                st.plotly_chart(fig_pop, use_container_width=True)
    else:
        st.info("Not enough historical data before the selected period to build a comparison.")

    st.write("")

    # ------------------------------------
    # Category Momentum (3-month trend)
    # ------------------------------------
    st.markdown("#### 🧭 Category Momentum (3-Month Trend)")
    st.caption(
        "Categories with a consistent rising or falling trend across the last 3 months — beyond the "
        "latest month vs. previous."
    )
    momentum = get_category_momentum(df_full, window=3)

    with st.container(border=True):
        if not momentum.empty:
            _render(top_momentum_insight(momentum))

            display_momentum = momentum.copy()
            display_momentum["Category"] = display_momentum["category_label"]
            display_momentum["Trend"] = display_momentum["direction"].apply(
                lambda d: f"{_MOMENTUM_ICONS.get(d, '→')} {d.title()}"
            )
            display_momentum["Last Month"] = display_momentum["last_month_value"].astype(float)
            display_momentum["3-Month Change"] = display_momentum["pct_change_over_window"] / 100.0

            st.dataframe(
                display_momentum[["Category", "Trend", "Last Month", "3-Month Change"]],
                column_config={
                    "Last Month": st.column_config.NumberColumn("Last Month", format="R$ %.2f"),
                    "3-Month Change": st.column_config.NumberColumn(
                        "3-Month Change", format="%.0f%%"
                    ),
                },
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(
                "Not enough monthly history yet to compute category momentum "
                "(needs 3+ months of data per category)."
            )

    st.write("")

    # ------------------------------------
    # Year-over-Year Comparison
    # ------------------------------------
    st.markdown("#### 📆 Year-over-Year Comparison")
    yoy = get_year_over_year_comparison(df_full)

    if not yoy.empty:
        with st.container(border=True):
            cur_year = int(yoy["current_year"].iloc[0])
            prev_year = int(yoy["previous_year"].iloc[0])
            total_cur = float(yoy["current_val"].sum())
            total_prev = float(yoy["previous_val"].sum())
            total_delta_pct = ((total_cur - total_prev) / total_prev * 100) if total_prev else 0.0

            y1, y2, y3 = st.columns(3)
            y1.metric(f"{cur_year} (Current)", format_currency_br(total_cur))
            y1.caption(f"Across {len(yoy)} overlapping month(s)")
            y2.metric(f"{prev_year} (Previous)", format_currency_br(total_prev))
            y2.caption("Same months, prior year")
            y3.metric(
                "Variation",
                format_currency_br(total_cur - total_prev),
                delta=f"{total_delta_pct:+.1f}%",
                delta_color="inverse",
            )
            y3.caption("Year-over-year")

            st.plotly_chart(build_yoy_figure(yoy), use_container_width=True)
    else:
        st.info("Year-over-Year comparison needs at least two years of invoice history.")

    st.write("")

    # ------------------------------------
    # Recurring Subscriptions & Fixed Costs
    # ------------------------------------
    st.markdown("#### 🔁 Recurring Subscriptions & Fixed Costs")
    st.caption(
        "Merchants billed consistently across multiple months (e.g. streaming, gym, insurance) — "
        "detected automatically from historical amount stability."
    )
    recurring = get_recurring_merchants(
        df_full, min_months=RECURRING_MIN_MONTHS, max_cv=RECURRING_MAX_CV
    )

    with st.container(border=True):
        if not recurring.empty:
            total_recurring = float(recurring["avg_monthly_cost"].sum())
            r1, r2, r3 = st.columns(3)
            r1.metric("Estimated Monthly Fixed Cost", format_currency_br(total_recurring))
            r2.metric("Recurring Merchants Detected", f"{len(recurring)}")
            r3.metric("Estimated Annual Impact", format_currency_br(total_recurring * 12))

            display_recurring = recurring.copy()
            display_recurring["Merchant"] = display_recurring["id"]
            display_recurring["Category"] = display_recurring["category_label"]
            display_recurring["Months Active"] = display_recurring["months_count"]
            display_recurring["Avg Monthly Cost"] = display_recurring["avg_monthly_cost"]
            display_recurring["Last Billed"] = display_recurring["last_amount"]
            display_recurring["Last Month"] = display_recurring["last_month"]
            display_recurring["Status"] = display_recurring["status"].map(
                {"Increased": "🔺 Increased", "Decreased": "🔻 Decreased", "Stable": "✅ Stable"}
            )

            st.dataframe(
                display_recurring[
                    [
                        "Merchant",
                        "Category",
                        "Months Active",
                        "Avg Monthly Cost",
                        "Last Billed",
                        "Last Month",
                        "Status",
                    ]
                ],
                column_config={
                    "Avg Monthly Cost": st.column_config.NumberColumn(
                        "Avg Monthly Cost", format="R$ %.2f"
                    ),
                    "Last Billed": st.column_config.NumberColumn("Last Billed", format="R$ %.2f"),
                },
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(
                "No recurring subscription-like merchants detected yet "
                "(needs at least 3 months of consistent billing history)."
            )

    st.write("")

    # ------------------------------------
    # Merchant Frequency Change
    # ------------------------------------
    st.markdown("#### 🔀 Merchant Frequency Change")
    st.caption(
        "Merchants whose recent buying frequency shifted notably from their historical baseline pace — "
        "unlike the recurring costs above, this flags a change in *how often* you use them."
    )
    freq_change = get_merchant_frequency_change(df_full)

    with st.container(border=True):
        if not freq_change.empty:
            _render(frequency_change_insight(freq_change))

            display_freq = freq_change.copy()
            display_freq["Merchant"] = display_freq["id"]
            display_freq["Category"] = display_freq["category_label"]
            display_freq["Recent Rate (tx/mo)"] = display_freq["recent_monthly_rate"].astype(float)
            display_freq["Baseline Rate (tx/mo)"] = display_freq["baseline_monthly_rate"].astype(
                float
            )
            display_freq["Change"] = display_freq["direction"].map(
                {"increased": "🔺 Increased", "decreased": "🔻 Decreased"}
            )
            display_freq["Change %"] = display_freq["change_pct"] / 100.0

            st.dataframe(
                display_freq[
                    [
                        "Merchant",
                        "Category",
                        "Recent Rate (tx/mo)",
                        "Baseline Rate (tx/mo)",
                        "Change",
                        "Change %",
                    ]
                ],
                column_config={
                    "Recent Rate (tx/mo)": st.column_config.NumberColumn(
                        "Recent Rate (tx/mo)", format="%.1f"
                    ),
                    "Baseline Rate (tx/mo)": st.column_config.NumberColumn(
                        "Baseline Rate (tx/mo)", format="%.1f"
                    ),
                    "Change %": st.column_config.NumberColumn("Change %", format="%.0f%%"),
                },
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(
                "No notable merchant frequency changes detected yet "
                "(needs enough purchase history to establish a baseline)."
            )

    st.write("")

    # ------------------------------------
    # Unusual Transactions (Anomaly Detection)
    # ------------------------------------
    st.markdown("#### ⚠️ Unusual Transactions Detected")
    st.caption(
        "Purchases significantly above the typical spending pattern for their category (statistical outliers)."
    )
    anomalies = get_spending_anomalies(
        df_expenses, z_threshold=ANOMALY_Z_THRESHOLD, min_category_tx=ANOMALY_MIN_CATEGORY_TX
    )

    with st.container(border=True):
        _render(anomalies_insight(anomalies))
        if not anomalies.empty:
            display_anom = anomalies.copy()
            display_anom["Purchase Date"] = pd.to_datetime(display_anom["date_buy"])
            display_anom["Merchant"] = display_anom["id"]
            display_anom["Category"] = display_anom["category_label"]
            display_anom["Amount"] = display_anom["cost"].astype(float)
            display_anom["Category Avg"] = display_anom["category_avg"].astype(float)
            display_anom["Deviation"] = display_anom["z_score"].apply(
                lambda z: f"{z:.1f}σ above average"
            )

            st.dataframe(
                display_anom[
                    ["Purchase Date", "Merchant", "Category", "Amount", "Category Avg", "Deviation"]
                ],
                column_config={
                    "Purchase Date": st.column_config.DateColumn(
                        "Purchase Date", format="YYYY-MM-DD"
                    ),
                    "Amount": st.column_config.NumberColumn("Amount", format="R$ %.2f"),
                    "Category Avg": st.column_config.NumberColumn("Category Avg", format="R$ %.2f"),
                },
                use_container_width=True,
                hide_index=True,
            )
