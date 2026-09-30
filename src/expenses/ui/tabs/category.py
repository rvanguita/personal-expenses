import pandas as pd
import streamlit as st

from src.expenses.analytics import get_category_momentum
from src.expenses.config import CATEGORY_CONFIG, DAY_OF_WEEK_LABELS_PT, format_currency_br
from src.expenses.ui.charts import build_ranked_bar_chart
from src.expenses.ui.figures import build_category_monthly_figure

_DOW_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_MONEY = st.column_config.NumberColumn(format="R$ %.2f")


def _category_options(df_filtered: pd.DataFrame) -> list[str]:
    cats = [c for c in sorted(df_filtered["category"].unique()) if c in CATEGORY_CONFIG]
    if "not_found" in cats:  # keep "Uncategorized" last
        cats.remove("not_found")
        cats.append("not_found")
    return cats


def _day_of_week_table(df_cat_exp: pd.DataFrame, cat_total: float) -> pd.DataFrame:
    agg = (
        df_cat_exp.assign(day_name=df_cat_exp["date_buy"].dt.day_name())
        .groupby("day_name")
        .agg(total=("cost", "sum"), count=("cost", "count"))
        .reindex(_DOW_ORDER)
        .fillna(0.0)
        .reset_index()
    )
    return pd.DataFrame(
        {
            "Day": agg["day_name"].map(lambda d: f"{d} ({DAY_OF_WEEK_LABELS_PT[d]})"),
            "Total": agg["total"].astype(float),
            "Transactions": agg["count"].astype(int),
            "Avg ticket": (agg["total"] / agg["count"].where(agg["count"] > 0)).fillna(0.0),
            "Share": agg["total"] / cat_total if cat_total > 0 else 0.0,
        }
    )


def render_category_tab(df_filtered: pd.DataFrame):
    """Categories: what is inside one category — size, trend, merchants and timing."""
    if df_filtered.empty:
        st.info("No transactions to analyze.")
        return

    options = _category_options(df_filtered)
    if not options:
        st.info("No categories available in the filtered dataset.")
        return

    select_col, _ = st.columns([1, 2])
    selected = select_col.selectbox(
        "Category",
        options=options,
        format_func=lambda c: CATEGORY_CONFIG[c]["label"],
    )
    meta = CATEGORY_CONFIG[selected]

    positive = df_filtered[df_filtered["cost"] > 0]
    df_cat_exp = positive[positive["category"] == selected].copy()
    cat_total = float(df_cat_exp["cost"].sum())
    cat_count = len(df_cat_exp)
    global_total = float(positive["cost"].sum())

    momentum = get_category_momentum(df_filtered, window=3)
    momentum_row = momentum[momentum["category"] == selected]
    momentum_delta = (
        f"{momentum_row.iloc[0]['pct_change_over_window']:+.1f}% over 3 months"
        if not momentum_row.empty
        else None
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Total",
        format_currency_br(cat_total),
        delta=momentum_delta,
        delta_color="inverse",
        help="Change compares the latest month with three months earlier.",
        border=True,
    )
    k2.metric(
        "Share of spending",
        f"{(cat_total / global_total * 100) if global_total > 0 else 0:.1f}%",
        border=True,
    )
    k3.metric("Transactions", f"{cat_count:,}", border=True)
    k4.metric(
        "Average ticket",
        format_currency_br(cat_total / cat_count if cat_count else 0.0),
        border=True,
    )

    left, right = st.columns([3, 2])
    with left, st.container(border=True):
        st.markdown("##### Monthly history")
        fig = build_category_monthly_figure(df_cat_exp, meta["label"], meta["color"])
        if fig is not None:
            st.plotly_chart(fig, width="stretch")
    with right, st.container(border=True):
        st.markdown("##### Top merchants")
        merchants = (
            df_cat_exp.groupby("id")["cost"]
            .sum()
            .reset_index()
            .sort_values(by="cost", ascending=False)
            .head(7)
        )
        if not merchants.empty:
            st.plotly_chart(
                build_ranked_bar_chart(merchants, "id", "cost", height=350), width="stretch"
            )

    with st.expander("Spending by day of week"):
        st.dataframe(
            _day_of_week_table(df_cat_exp, cat_total),
            column_config={
                "Total": _MONEY,
                "Avg ticket": _MONEY,
                "Share": st.column_config.NumberColumn(format="percent"),
            },
            width="stretch",
            hide_index=True,
        )

    with st.expander("Largest transactions"):
        top_tx = df_cat_exp.sort_values(by="cost", ascending=False).head(15)
        st.dataframe(
            pd.DataFrame(
                {
                    "Invoice date": pd.to_datetime(top_tx["date"]),
                    "Purchase date": pd.to_datetime(top_tx["date_buy"]),
                    "Merchant": top_tx["id"],
                    "Amount": top_tx["cost"].astype(float),
                    "Installments": [
                        f"{int(i)}/{int(t)}" if t > 1 else "Single payment"
                        for i, t in zip(
                            top_tx["installment"], top_tx["total_installments"], strict=True
                        )
                    ],
                }
            ),
            column_config={
                "Invoice date": st.column_config.DateColumn(format="YYYY-MM-DD"),
                "Purchase date": st.column_config.DateColumn(format="YYYY-MM-DD"),
                "Amount": _MONEY,
            },
            width="stretch",
            hide_index=True,
        )
