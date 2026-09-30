import pandas as pd
import streamlit as st

from expenses.analytics import (
    get_merchant_frequency_change,
    get_recurring_merchants,
    get_spending_anomalies,
)
from expenses.config import (
    ANOMALY_MIN_CATEGORY_TX,
    ANOMALY_Z_THRESHOLD,
    RECURRING_MAX_CV,
    RECURRING_MIN_MONTHS,
    format_currency_br,
)
from expenses_streamlit.styles import section

_MONEY = st.column_config.NumberColumn(format="R$ %.2f")
_STATUS = {"Increased": "▲ Increased", "Decreased": "▼ Decreased", "Stable": "Stable"}


def _uncategorized(df_expenses: pd.DataFrame) -> tuple[pd.DataFrame, float, float]:
    """(per-merchant table, uncategorized total, share of positive spending in %)."""
    positive = df_expenses[df_expenses["cost"] > 0]
    nf = positive[positive["category"] == "not_found"]
    total = float(positive["cost"].sum())
    nf_total = float(nf["cost"].sum())
    table = (
        nf.groupby("id")
        .agg(transactions=("cost", "count"), total=("cost", "sum"), last=("date_buy", "max"))
        .reset_index()
        .sort_values("total", ascending=False)
        .rename(
            columns={
                "id": "Merchant",
                "transactions": "Transactions",
                "total": "Total",
                "last": "Last purchase",
            }
        )
    )
    return table, nf_total, (nf_total / total * 100) if total > 0 else 0.0


def render_watchlist_tab(df_filtered: pd.DataFrame, df_full: pd.DataFrame):
    """Watchlist: recurring charges, unusual purchases and uncategorized spending."""
    if df_filtered.empty:
        st.info("No transactions found with the selected filters.")
        return

    df_expenses = df_filtered[~df_filtered["is_payment"]].copy()
    recurring = get_recurring_merchants(
        df_full, min_months=RECURRING_MIN_MONTHS, max_cv=RECURRING_MAX_CV
    )
    anomalies = get_spending_anomalies(
        df_expenses, z_threshold=ANOMALY_Z_THRESHOLD, min_category_tx=ANOMALY_MIN_CATEGORY_TX
    )
    uncategorized, nf_total, nf_share = _uncategorized(df_expenses)
    fixed_cost = float(recurring["avg_monthly_cost"].sum()) if not recurring.empty else 0.0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Fixed monthly cost",
        format_currency_br(fixed_cost),
        help=f"Recurring charges, about {format_currency_br(fixed_cost * 12)} a year.",
        border=True,
    )
    k2.metric("Recurring merchants", f"{len(recurring)}", border=True)
    k3.metric(
        "Unusual purchases",
        f"{len(anomalies)}",
        help=f"More than {ANOMALY_Z_THRESHOLD}σ above their category average (selected period).",
        border=True,
    )
    k4.metric(
        "Uncategorized",
        format_currency_br(nf_total),
        help=f"{nf_share:.1f}% of spending in the selected period.",
        border=True,
    )

    section(
        "Recurring charges",
        f"Billed in {RECURRING_MIN_MONTHS}+ months with a stable amount (subscriptions, "
        "insurance, gym). Uses the full history.",
    )
    if recurring.empty:
        st.caption("None detected yet.")
    else:
        st.dataframe(
            pd.DataFrame(
                {
                    "Merchant": recurring["id"],
                    "Category": recurring["category_label"],
                    "Avg / month": recurring["avg_monthly_cost"].astype(float),
                    "Last charge": recurring["last_amount"].astype(float),
                    "Last month": recurring["last_month"],
                    "Months": recurring["months_count"],
                    "Status": recurring["status"].map(_STATUS),
                }
            ).sort_values("Avg / month", ascending=False),
            column_config={"Avg / month": _MONEY, "Last charge": _MONEY},
            width="stretch",
            hide_index=True,
        )

    section("Unusual purchases", "Well above the typical amount for their category.")
    if anomalies.empty:
        st.caption("Nothing unusual in the selected period.")
    else:
        st.dataframe(
            pd.DataFrame(
                {
                    "Date": pd.to_datetime(anomalies["date_buy"]),
                    "Merchant": anomalies["id"],
                    "Category": anomalies["category_label"],
                    "Amount": anomalies["cost"].astype(float),
                    "Category avg": anomalies["category_avg"].astype(float),
                    "Deviation": anomalies["z_score"].map(lambda z: f"{z:.1f}σ"),
                }
            ),
            column_config={
                "Date": st.column_config.DateColumn(format="YYYY-MM-DD"),
                "Amount": _MONEY,
                "Category avg": _MONEY,
            },
            width="stretch",
            hide_index=True,
        )

    section("Uncategorized spending", "Classify these merchants in the **Categorize** tab.")
    if uncategorized.empty:
        st.caption("Everything in the selected period has a category.")
    else:
        st.dataframe(
            uncategorized,
            column_config={
                "Total": _MONEY,
                "Last purchase": st.column_config.DateColumn(format="YYYY-MM-DD"),
            },
            width="stretch",
            hide_index=True,
        )

    freq = get_merchant_frequency_change(df_full)
    with st.expander("Merchants you now buy from more or less often"):
        if freq.empty:
            st.caption("Not enough history to establish a baseline.")
        else:
            st.dataframe(
                pd.DataFrame(
                    {
                        "Merchant": freq["id"],
                        "Category": freq["category_label"],
                        "Recent (tx/month)": freq["recent_monthly_rate"].astype(float),
                        "Baseline (tx/month)": freq["baseline_monthly_rate"].astype(float),
                        "Change": freq["change_pct"] / 100.0,
                    }
                ),
                column_config={
                    "Recent (tx/month)": st.column_config.NumberColumn(format="%.1f"),
                    "Baseline (tx/month)": st.column_config.NumberColumn(format="%.1f"),
                    "Change": st.column_config.NumberColumn(format="percent"),
                },
                width="stretch",
                hide_index=True,
            )
