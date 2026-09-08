import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.expenses.analytics import get_category_momentum, get_day_of_week_spending
from src.expenses.config import CATEGORY_CONFIG, DAY_OF_WEEK_LABELS_PT, format_currency_br
from src.expenses.ui.charts import (
    add_total_line_trace,
    amounts_hidden,
    apply_chart_theme,
    build_emphasis_bar_colors,
    build_ranked_bar_chart,
)
from src.expenses.ui.styles import render_insight_card

_MOMENTUM_META = {
    "rising": {"icon": "📈", "severity": "warning", "verb": "trending up"},
    "falling": {"icon": "📉", "severity": "good", "verb": "trending down"},
    "stable": {"icon": "➡️", "severity": "info", "verb": "stable"},
}


def render_category_tab(df_filtered: pd.DataFrame):
    """Renders the Category Analysis, deep-dive drill-down, peak spending days, and Uncategorized (not_found) section."""
    if df_filtered.empty:
        st.info("No transactions to analyze.")
        return

    st.markdown("### 🔍 Category Breakdown & Analysis")

    # -------------------------------------------------------------
    # ❓ Dedicated Section: Uncategorized Expenses (not_found)
    # -------------------------------------------------------------
    df_not_found = df_filtered[df_filtered["category"] == "not_found"]
    df_not_found_exp = df_not_found[df_not_found["cost"] > 0]
    total_exp = float(df_filtered[df_filtered["cost"] > 0]["cost"].sum())

    if not df_not_found_exp.empty:
        nf_total = float(df_not_found_exp["cost"].sum())
        nf_count = len(df_not_found_exp)
        nf_share = (nf_total / total_exp * 100) if total_exp > 0 else 0.0

        with st.expander(
            f"⚠️ ❓ **Uncategorized Expenses (`not_found`): {format_currency_br(nf_total)} ({nf_count} transactions, {nf_share:.1f}% of total)**",
            expanded=True,
        ):
            st.caption(
                "These transactions currently have no assigned category. You can auto-match or classify them using **Gemini AI** in the **🏷️ AI Categorization & Matching** tab."
            )

            nf_c1, nf_c2, nf_c3 = st.columns(3)
            nf_c1.metric("Uncategorized Total", format_currency_br(nf_total))
            nf_c2.metric("Pending Transactions", f"{nf_count:,}")
            nf_c3.metric("Share of Spending", f"{nf_share:.1f}%")

            col_nf_m, col_nf_t = st.columns([1, 1])
            with col_nf_m:
                st.markdown("##### Top Uncategorized Merchants")
                top_nf_merchants = (
                    df_not_found_exp.groupby("id")["cost"]
                    .sum()
                    .reset_index()
                    .sort_values(by="cost", ascending=False)
                    .head(5)
                )
                if not top_nf_merchants.empty:
                    top_nf_merchants["cost_fmt"] = top_nf_merchants["cost"].apply(
                        format_currency_br
                    )
                    st.dataframe(
                        top_nf_merchants.rename(
                            columns={"id": "Merchant", "cost_fmt": "Total Amount"}
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

            with col_nf_t:
                st.markdown("##### Latest Uncategorized Items")
                latest_nf = df_not_found_exp.sort_values(by="date_buy", ascending=False).head(5)
                display_latest = latest_nf[["date_buy", "id", "cost"]].copy()
                display_latest["Purchase Date"] = pd.to_datetime(display_latest["date_buy"])
                display_latest["Merchant"] = display_latest["id"]
                display_latest["Amount"] = display_latest["cost"].astype(float)
                st.dataframe(
                    display_latest[["Purchase Date", "Merchant", "Amount"]],
                    column_config={
                        "Purchase Date": st.column_config.DateColumn(
                            "Purchase Date", format="YYYY-MM-DD"
                        ),
                        "Merchant": st.column_config.TextColumn("Merchant"),
                        "Amount": st.column_config.NumberColumn("Amount", format="R$ %.2f"),
                    },
                    use_container_width=True,
                    hide_index=True,
                )

        st.write("")

    # -------------------------------------------------------------
    # 🔍 Deep Dive by Category Selector
    # -------------------------------------------------------------
    available_cats = [c for c in sorted(df_filtered["category"].unique()) if c in CATEGORY_CONFIG]

    if not available_cats:
        st.info("No categories available in the filtered dataset.")
        return

    # Put 'not_found' at the end of the selectbox options if present
    if "not_found" in available_cats:
        available_cats.remove("not_found")
        available_cats.append("not_found")

    selected_detail_cat = st.selectbox(
        "Select a Category to Analyze in Detail:",
        options=available_cats,
        format_func=lambda c: f"{CATEGORY_CONFIG[c]['icon']} {CATEGORY_CONFIG[c]['label']}",
    )

    df_cat = df_filtered[df_filtered["category"] == selected_detail_cat]
    df_cat_exp = df_cat[df_cat["cost"] > 0].copy()

    cat_total = float(df_cat_exp["cost"].sum())
    cat_count = len(df_cat_exp)
    cat_avg = cat_total / cat_count if cat_count > 0 else 0.0
    global_exp = float(df_filtered[df_filtered["cost"] > 0]["cost"].sum())
    cat_share = (cat_total / global_exp * 100) if global_exp > 0 else 0.0

    # Momentum callout for the selected category (3-month trend, computed on the filtered dataset)
    momentum_df = get_category_momentum(df_filtered, window=3)
    cat_momentum = momentum_df[momentum_df["category"] == selected_detail_cat]
    if not cat_momentum.empty:
        m = cat_momentum.iloc[0]
        meta = _MOMENTUM_META[m["direction"]]
        render_insight_card(
            meta["icon"],
            f"{CATEGORY_CONFIG[selected_detail_cat]['label']} is {meta['verb']}",
            f"Changed **{m['pct_change_over_window']:+.1f}%** over the last 3 months (now "
            f"**{format_currency_br(m['last_month_value'])}**/month).",
            severity=meta["severity"],
        )

    # Calculate Peak Day of Month, Peak Day of Week, and Highest Single Date
    peak_date_str = "N/A"
    peak_date_val = 0.0
    if not df_cat_exp.empty and "date_buy" in df_cat_exp.columns:
        daily_cat = df_cat_exp.groupby(df_cat_exp["date_buy"].dt.date)["cost"].sum().reset_index()
        if not daily_cat.empty:
            max_day_row = daily_cat.sort_values(by="cost", ascending=False).iloc[0]
            peak_date_str = pd.to_datetime(max_day_row["date_buy"]).strftime("%d/%m/%Y")
            peak_date_val = float(max_day_row["cost"])

    peak_dow_str = "N/A"
    peak_dow_val = 0.0
    if not df_cat_exp.empty and "day_of_week" in df_cat_exp.columns:
        dow_cat = df_cat_exp.groupby("day_of_week")["cost"].sum().reset_index()
        if not dow_cat.empty:
            max_dow_row = dow_cat.sort_values(by="cost", ascending=False).iloc[0]
            peak_dow_str = str(max_dow_row["day_of_week"])
            peak_dow_val = float(max_dow_row["cost"])

    # Category KPI summary cards including Peak Spending Day
    st.markdown("#### 📊 Category KPIs")
    with st.container(border=True):
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("Category Total", format_currency_br(cat_total))
        k2.metric("Transactions", f"{cat_count:,}")
        k3.metric("Avg Ticket", format_currency_br(cat_avg))
        k4.metric("Global Share", f"{cat_share:.1f}%")
        k5.metric("Peak Day (Date)", peak_date_str, format_currency_br(peak_date_val))
        k6.metric("Peak Day of Week", peak_dow_str, format_currency_br(peak_dow_val))

    st.write("")

    col_cat_left, col_cat_right = st.columns([3, 2])

    with col_cat_left:
        with st.container(border=True):
            st.markdown(f"#### Monthly History: {CATEGORY_CONFIG[selected_detail_cat]['label']}")
            cat_monthly = (
                df_cat_exp.groupby("year_month")["cost"]
                .sum()
                .reset_index()
                .sort_values(by="year_month", ascending=True)
            )

            if not cat_monthly.empty:
                sorted_cat_months = cat_monthly["year_month"].tolist()
                max_cat_y = float(cat_monthly["cost"].max())
                cat_color = CATEGORY_CONFIG[selected_detail_cat]["color"]

                fig_cat_time = go.Figure()
                add_total_line_trace(
                    fig_cat_time,
                    cat_monthly["year_month"],
                    cat_monthly["cost"],
                    name=CATEGORY_CONFIG[selected_detail_cat]["label"],
                    color=cat_color,
                    dash="solid",
                )
                apply_chart_theme(fig_cat_time, height=350, legend="hidden")
                fig_cat_time.update_layout(
                    xaxis={
                        "type": "category",
                        "categoryorder": "array",
                        "categoryarray": sorted_cat_months,
                        "title": "",
                        "tickangle": -45,
                    },
                    yaxis={"title": "Amount (R$)", "range": [0, max_cat_y * 1.25]},
                )
                st.plotly_chart(fig_cat_time, use_container_width=True)

    with col_cat_right:
        with st.container(border=True):
            st.markdown("#### Top Merchants in Category")
            cat_merchants = (
                df_cat_exp.groupby("id")["cost"]
                .sum()
                .reset_index()
                .sort_values(by="cost", ascending=False)
                .head(7)
            )

            if not cat_merchants.empty:
                fig_cat_m = build_ranked_bar_chart(cat_merchants, "id", "cost", height=340)
                st.plotly_chart(fig_cat_m, use_container_width=True)

    # -------------------------------------------------------------
    # 📅 Spending Pattern by Day of Week (Monday to Sunday)
    # -------------------------------------------------------------
    st.markdown(
        f"#### 📅 Spending Pattern by Day of Week: {CATEGORY_CONFIG[selected_detail_cat]['label']}"
    )
    dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    df_cat_exp["day_name"] = df_cat_exp["date_buy"].dt.day_name()

    # Calculate sum and counts for every day of the week
    dow_agg = (
        df_cat_exp.groupby("day_name")
        .agg(
            total_sum=("cost", "sum"),
            tx_count=("cost", "count"),
        )
        .reindex(dow_order)
        .fillna(0.0)
        .reset_index()
    )

    dow_agg["avg_ticket"] = dow_agg.apply(
        lambda r: (r["total_sum"] / r["tx_count"]) if r["tx_count"] > 0 else 0.0, axis=1
    )
    dow_agg["share_pct"] = dow_agg["total_sum"].apply(
        lambda s: (s / cat_total * 100) if cat_total > 0 else 0.0
    )

    with st.container(border=True):
        # 7-Column Metric Cards for Monday to Sunday
        c_mon, c_tue, c_wed, c_thu, c_fri, c_sat, c_sun = st.columns(7)
        metric_cols = [c_mon, c_tue, c_wed, c_thu, c_fri, c_sat, c_sun]

        for idx, dow_name in enumerate(dow_order):
            row_dow = dow_agg[dow_agg["day_name"] == dow_name].iloc[0]
            val_sum = float(row_dow["total_sum"])
            tx_cnt = int(row_dow["tx_count"])
            pct = float(row_dow["share_pct"])
            metric_cols[idx].metric(
                label=f"{dow_name[:3]} ({DAY_OF_WEEK_LABELS_PT[dow_name][:3]})",
                value=format_currency_br(val_sum),
                delta=f"{tx_cnt} tx ({pct:.1f}%)",
                delta_color="off",
            )

    st.write("")

    col_dw_left, col_dw_right = st.columns([3, 2])

    with col_dw_left:
        with st.container(border=True):
            st.markdown("##### 📊 Spending Pattern by Day of Week (Chart)")
            day_spending = get_day_of_week_spending(df_cat_exp)

            if not day_spending.empty:
                peak_day = day_spending.sort_values(by="cost", ascending=False).iloc[0][
                    "dia_semana"
                ]
                bar_colors = build_emphasis_bar_colors(
                    day_spending["dia_semana"].tolist(), peak_day
                )
                max_day_spent = float(day_spending["cost"].max())

                fig_days = px.bar(
                    day_spending,
                    x="dia_semana",
                    y="cost",
                    text=None
                    if amounts_hidden()
                    else [format_currency_br(v) for v in day_spending["cost"]],
                    labels={"cost": "Total Spent (R$)", "dia_semana": "Day of Week"},
                )
                fig_days.update_traces(
                    marker_color=bar_colors,
                    textposition="outside",
                    cliponaxis=False,
                    textfont={"size": 11},
                )
                apply_chart_theme(fig_days, height=340, legend="hidden")
                fig_days.update_layout(
                    xaxis={"title": ""},
                    yaxis={"range": [0, max_day_spent * 1.25], "title": "Total (R$)"},
                )
                st.plotly_chart(fig_days, use_container_width=True)

    with col_dw_right:
        with st.container(border=True):
            st.markdown("##### 📋 Spending Pattern Breakdown (Table)")
            df_dow_table = dow_agg.copy()
            df_dow_table["Day"] = df_dow_table["day_name"].apply(
                lambda d: f"{d} ({DAY_OF_WEEK_LABELS_PT[d]})"
            )
            df_dow_table["Total Spent"] = df_dow_table["total_sum"].astype(float)
            df_dow_table["Transactions"] = df_dow_table["tx_count"].astype(int)
            df_dow_table["Avg Ticket"] = df_dow_table["avg_ticket"].astype(float)
            df_dow_table["% Share"] = df_dow_table["share_pct"] / 100.0

            st.dataframe(
                df_dow_table[["Day", "Total Spent", "Transactions", "Avg Ticket", "% Share"]],
                column_config={
                    "Day": st.column_config.TextColumn("Day of Week"),
                    "Total Spent": st.column_config.NumberColumn("Total Spent", format="R$ %.2f"),
                    "Transactions": st.column_config.NumberColumn("Transactions", format="%d"),
                    "Avg Ticket": st.column_config.NumberColumn("Avg Ticket", format="R$ %.2f"),
                    "% Share": st.column_config.NumberColumn("% Share", format="%.1f%%"),
                },
                use_container_width=True,
                hide_index=True,
            )

    st.write("")

    # -------------------------------------------------------------
    # 📋 Largest Transactions in this Category
    # -------------------------------------------------------------
    st.markdown("#### 📋 Largest Transactions in this Category")
    with st.container(border=True):
        top_tx_cat = df_cat_exp.sort_values(by="cost", ascending=False).head(15)
        display_top_tx = top_tx_cat[
            ["date", "date_buy", "id", "cost", "installment", "total_installments"]
        ].copy()
        display_top_tx["Invoice Date"] = pd.to_datetime(display_top_tx["date"])
        display_top_tx["Purchase Date"] = pd.to_datetime(display_top_tx["date_buy"])
        display_top_tx["Merchant"] = display_top_tx["id"]
        display_top_tx["Amount"] = display_top_tx["cost"].astype(float)
        display_top_tx["Installments"] = display_top_tx.apply(
            lambda r: (
                f"{int(r['installment'])}/{int(r['total_installments'])}"
                if r["total_installments"] > 1
                else "Single Payment"
            ),
            axis=1,
        )
        st.dataframe(
            display_top_tx[["Invoice Date", "Purchase Date", "Merchant", "Amount", "Installments"]],
            column_config={
                "Invoice Date": st.column_config.DateColumn("Invoice Date", format="YYYY-MM-DD"),
                "Purchase Date": st.column_config.DateColumn("Purchase Date", format="YYYY-MM-DD"),
                "Merchant": st.column_config.TextColumn("Merchant"),
                "Amount": st.column_config.NumberColumn("Amount", format="R$ %.2f"),
                "Installments": st.column_config.TextColumn("Installments"),
            },
            use_container_width=True,
            hide_index=True,
        )
