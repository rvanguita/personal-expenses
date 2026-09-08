import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.expenses.analytics import (
    calculate_kpis,
    get_day_of_week_spending,
    get_financial_health_score,
    get_month_pace_projection,
    get_monthly_grouped,
    get_next_month_commitment_metrics,
    get_spending_anomalies,
    get_top_merchants,
)
from src.expenses.config import (
    ANOMALY_MIN_CATEGORY_TX,
    ANOMALY_Z_THRESHOLD,
    CATEGORY_COLOR_MAP,
    INSTALLMENT_BURDEN_WARNING_PCT,
    REFERENCE_BUDGET_LIMIT,
    format_currency_br,
    format_currency_md,
    get_category_color,
)
from src.expenses.ui.charts import (
    add_total_line_trace,
    amounts_hidden,
    apply_chart_theme,
    build_emphasis_bar_colors,
    build_ranked_bar_chart,
)
from src.expenses.ui.styles import render_insight_card

_HEALTH_RATING_META = {
    "Excellent": {"icon": "💚", "severity": "good"},
    "Good": {"icon": "✅", "severity": "good"},
    "Fair": {"icon": "🟡", "severity": "warning"},
    "At Risk": {"icon": "🔴", "severity": "critical"},
}
_HEALTH_FACTOR_LABELS = {
    "installment_burden": "installment burden",
    "anomalies": "unusual transactions",
    "budget_proximity": "upcoming budget proximity",
    "spend_volatility": "month-over-month volatility",
}


def render_dashboard_tab(df_filtered: pd.DataFrame, df_full: pd.DataFrame):
    """Renders the General Dashboard tab with KPIs, remodeled timeline controls, and Plotly charts."""
    if df_filtered.empty:
        st.info("No transactions found with the selected filters.")
        return

    # Filter out payment settlements (Pagamentos Validos Normais)
    df_expenses = (
        df_filtered[~df_filtered["is_payment"]].copy()
        if "is_payment" in df_filtered.columns
        else df_filtered[
            ~df_filtered["id"].str.contains(
                r"PAGAMENTO|PAGTO|PAYMENT|PAGAMENTOS VALIDOS", case=False, regex=True, na=False
            )
        ].copy()
    )

    kpis = calculate_kpis(df_filtered, df_full)

    # ------------------------------------
    # Financial Health Score
    # ------------------------------------
    health = get_financial_health_score(df_full)
    if health["has_data"]:
        rating_meta = _HEALTH_RATING_META[health["rating"]]
        top_factor_label = _HEALTH_FACTOR_LABELS.get(health["top_factor"], health["top_factor"])
        top_factor_score = health["components"].get(health["top_factor"], 0)
        render_insight_card(
            rating_meta["icon"],
            f"Financial Health Score: {health['score']}/100 ({health['rating']})",
            f"Composite score across installment burden, anomalies, upcoming budget proximity, and "
            f"spending volatility. Weakest factor: **{top_factor_label}** ({top_factor_score:.0f}/100).",
            severity=rating_meta["severity"],
        )

    # ------------------------------------
    # Next Month Installment Commitment Alert
    # ------------------------------------
    next_metrics = get_next_month_commitment_metrics(
        df_full, reference_limit=REFERENCE_BUDGET_LIMIT
    )
    if next_metrics["has_data"]:
        next_cost_md = format_currency_md(next_metrics["next_month_cost"])
        diff_val_md = format_currency_md(abs(next_metrics["diff_from_limit"]))
        limit_md = format_currency_md(REFERENCE_BUDGET_LIMIT)

        if next_metrics["is_over_limit"]:
            render_insight_card(
                "⚠️",
                f"Upcoming Month Budget Warning ({next_metrics['next_month']})",
                f"**{next_cost_md}** ({next_metrics['pct_of_limit']:.1f}% of the {limit_md} reference "
                f"limit) is already committed across **{next_metrics['num_installments']}** active "
                f"installment(s) — **+{diff_val_md} above** the reference limit.",
                severity="critical",
            )
        else:
            render_insight_card(
                "🔒",
                f"Upcoming Month Budget On Track ({next_metrics['next_month']})",
                f"**{next_cost_md}** ({next_metrics['pct_of_limit']:.1f}% of the {limit_md} reference "
                f"limit) is already committed across **{next_metrics['num_installments']}** active "
                f"installment(s) — **{diff_val_md} remaining** within budget.",
                severity="good",
            )

    st.write("")

    # ------------------------------------
    # Automated Insights
    # ------------------------------------
    st.markdown("#### 💡 Automated Insights")
    with st.container(border=True):
        in1, in2, in3, in4, in5 = st.columns(5)

        with in1:
            render_insight_card(
                "🎯",
                "Top Expense Driver",
                f"**{kpis['top_cat_name']}** consumes **{kpis['top_cat_pct']:.1f}%** of your total net "
                "spending.",
                severity="info",
            )

        with in2:
            if kpis["mom_delta_pct"] > 0:
                render_insight_card(
                    "📈",
                    "Spending Increased",
                    f"Your latest invoice is **{kpis['mom_delta_pct']:.1f}%** higher than the previous "
                    "one.",
                    severity="warning",
                )
            elif kpis["mom_delta_pct"] < 0:
                render_insight_card(
                    "📉",
                    "Spending Decreased",
                    f"Great job! Your latest invoice dropped by **{abs(kpis['mom_delta_pct']):.1f}%**.",
                    severity="good",
                )
            else:
                render_insight_card(
                    "⚖️",
                    "Spending Stable",
                    "Your latest invoice is exactly the same as the previous one.",
                    severity="info",
                )

        with in3:
            if kpis["installment_pct"] > INSTALLMENT_BURDEN_WARNING_PCT:
                render_insight_card(
                    "💳",
                    "High Installment Burden",
                    f"**{kpis['installment_pct']:.1f}%** of your spending is tied up in installments.",
                    severity="warning",
                )
            else:
                render_insight_card(
                    "💳",
                    "Healthy Installment Ratio",
                    f"Only **{kpis['installment_pct']:.1f}%** of your spending is tied up in "
                    "installments.",
                    severity="good",
                )

        with in4:
            anomalies = get_spending_anomalies(
                df_expenses,
                z_threshold=ANOMALY_Z_THRESHOLD,
                min_category_tx=ANOMALY_MIN_CATEGORY_TX,
            )
            if not anomalies.empty:
                render_insight_card(
                    "⚠️",
                    f"{len(anomalies)} Unusual Transaction(s)",
                    "Some purchases are well above their category's typical pattern. See the "
                    "**📈 Trends & Insights** tab for details.",
                    severity="warning",
                )
            else:
                render_insight_card(
                    "✅",
                    "No Anomalies Detected",
                    "All transactions fall within the expected spending pattern for their category.",
                    severity="good",
                )

        with in5:
            pace = get_month_pace_projection(df_full)
            if not pace["has_data"]:
                render_insight_card(
                    "📆",
                    "Spending Pace",
                    "Not enough data yet to project this month's pace.",
                    severity="info",
                )
            elif pace["status"] == "hot":
                render_insight_card(
                    "🔥",
                    "Spending Pace Running Hot",
                    f"**{pace['current_month']}** is projected to reach "
                    f"**{format_currency_md(pace['projected_total'])}** "
                    f"({pace['pace_delta_pct']:+.1f}% vs your recent average).",
                    severity="warning",
                )
            elif pace["status"] == "cold":
                render_insight_card(
                    "🧊",
                    "Spending Pace Running Cold",
                    f"**{pace['current_month']}** is projected to reach "
                    f"**{format_currency_md(pace['projected_total'])}** "
                    f"({pace['pace_delta_pct']:+.1f}% vs your recent average).",
                    severity="good",
                )
            else:
                render_insight_card(
                    "📆",
                    "Spending Pace Normal",
                    f"**{pace['current_month']}** is tracking close to your recent monthly average "
                    f"(projected **{format_currency_md(pace['projected_total'])}**).",
                    severity="info",
                )

    st.write("")

    # ------------------------------------
    # Key Performance Indicators (KPIs)
    # ------------------------------------
    st.markdown("#### 📊 Key Performance Indicators")
    with st.container(border=True):
        kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)

        kpi1.metric("💰 Net Spent", format_currency_br(kpis["total_spent"]))
        if kpis["total_refunds"] < 0:
            kpi1.caption(
                f"Gross: {format_currency_br(kpis['gross_spent'])} | Refunds: {format_currency_br(kpis['total_refunds'])}"
            )
        else:
            kpi1.caption(f"Invoices: {kpis['num_months']} selected")

        kpi2.metric("📅 Monthly Avg", format_currency_br(kpis["avg_monthly_spent"]))
        kpi2.caption("Avg net per invoice")

        delta_str = f"{kpis['mom_delta_pct']:+.1f}% ({format_currency_br(kpis['mom_delta_val'])})"
        kpi3.metric(
            "📈 MoM Variation",
            format_currency_br(kpis["latest_m_val"]),
            delta=delta_str,
            delta_color="inverse",
        )
        kpi3.caption("Latest vs previous")

        kpi4.metric("🏆 Top Category", kpis["top_cat_name"])
        kpi4.caption(f"{format_currency_md(kpis['top_cat_val'])} ({kpis['top_cat_pct']:.1f}%)")

        kpi5.metric("🧾 Transactions", f"{kpis['total_tx']:,}")
        kpi5.caption(f"Avg Ticket: {format_currency_md(kpis['avg_tx'])}")

        kpi6.metric("💳 Installments", f"{kpis['installment_pct']:.1f}%")
        kpi6.caption(f"{format_currency_md(kpis['installment_spent'])} total")

    # ------------------------------------
    # Consolidated Monthly Invoice Totals Table (by exact invoice 'date')
    # ------------------------------------
    with st.expander(
        "📋 **Detailed Monthly Invoice Totals (Grouped by Invoice `date`)**", expanded=False
    ):
        df_invoice_summary = (
            df_expenses.groupby(["year_month", "date"])
            .agg(
                tx_count=("cost", "count"),
                gross_cost=("cost", lambda s: s[s > 0].sum()),
                refunds=("cost", lambda s: s[s < 0].sum()),
                net_cost=("cost", "sum"),
            )
            .reset_index()
            .sort_values(by="date", ascending=False)
        )
        df_invoice_display = df_invoice_summary.copy()
        df_invoice_display["Invoice Month"] = df_invoice_display["year_month"]
        df_invoice_display["Invoice Date"] = pd.to_datetime(df_invoice_display["date"])
        df_invoice_display["Transactions"] = df_invoice_display["tx_count"].astype(int)
        df_invoice_display["Gross Purchases"] = df_invoice_display["gross_cost"].astype(float)
        df_invoice_display["Refunds / Estornos"] = df_invoice_display["refunds"].astype(float)
        df_invoice_display["Net Invoice Total (Valor da Fatura)"] = df_invoice_display[
            "net_cost"
        ].astype(float)

        st.dataframe(
            df_invoice_display[
                [
                    "Invoice Month",
                    "Invoice Date",
                    "Transactions",
                    "Gross Purchases",
                    "Refunds / Estornos",
                    "Net Invoice Total (Valor da Fatura)",
                ]
            ],
            column_config={
                "Invoice Month": st.column_config.TextColumn("Invoice Month"),
                "Invoice Date": st.column_config.DateColumn("Invoice Date", format="YYYY-MM-DD"),
                "Transactions": st.column_config.NumberColumn("Transactions", format="%d"),
                "Gross Purchases": st.column_config.NumberColumn(
                    "Gross Purchases", format="R$ %.2f"
                ),
                "Refunds / Estornos": st.column_config.NumberColumn(
                    "Refunds / Estornos", format="R$ %.2f"
                ),
                "Net Invoice Total (Valor da Fatura)": st.column_config.NumberColumn(
                    "Net Invoice Total (Valor da Fatura)", format="R$ %.2f"
                ),
            },
            use_container_width=True,
            hide_index=True,
        )

    st.write("")

    # ------------------------------------
    # Primary Charts (Row 1)
    # ------------------------------------
    c1, c2 = st.columns([3, 2])

    with c1:
        with st.container(border=True):
            st.markdown("#### 📊 Monthly Expense Evolution by Category")

            # Remodeled Timeline Controls Toolbar
            col_ctl1, col_ctl2 = st.columns([3, 2])
            with col_ctl1:
                timeline_mode = st.segmented_control(
                    "Group Timeline By:",
                    options=["📅 Invoice Date (`date`)", "🛒 Purchase Date (`date_buy`)"],
                    default="📅 Invoice Date (`date`)",
                    key="seg_timeline_mode",
                )
                if not timeline_mode:
                    timeline_mode = "📅 Invoice Date (`date`)"

            with col_ctl2:
                chart_style = st.segmented_control(
                    "Chart View:",
                    options=["📊 Stacked", "📈 Trend Lines"],
                    default="📊 Stacked",
                    key="seg_chart_style",
                )
                if not chart_style:
                    chart_style = "📊 Stacked"

            # Active date basis
            is_invoice_date = "Invoice Date" in timeline_mode
            group_col = "year_month" if is_invoice_date else "buy_year_month"
            timeline_desc = (
                "Grouping expenses by credit card invoice billing cycle date (`date`)"
                if is_invoice_date
                else "Grouping expenses by actual transaction date (`date_buy`)"
            )
            st.caption(f"ℹ️ *{timeline_desc}*")

            df_grouped_month = get_monthly_grouped(df_expenses, group_col=group_col)

            if not df_grouped_month.empty:
                month_totals = (
                    df_expenses.groupby(group_col)["cost"]
                    .sum()
                    .reset_index()
                    .sort_values(by=group_col, ascending=True)
                )
                sorted_months = sorted(df_expenses[group_col].dropna().unique().tolist())
                max_y = float(month_totals["cost"].max()) if not month_totals.empty else 100.0
                month_totals["moving_avg"] = (
                    month_totals["cost"].rolling(window=3, min_periods=1).mean()
                )

                if chart_style == "📈 Trend Lines":
                    fig_bar = px.line(
                        df_grouped_month,
                        x=group_col,
                        y="cost",
                        color="category_label",
                        color_discrete_map=CATEGORY_COLOR_MAP,
                        category_orders={group_col: sorted_months},
                        markers=True,
                        labels={
                            "cost": "Amount (R$)",
                            group_col: "Month",
                            "category_label": "Category",
                        },
                        hover_data={"cost": ":,.2f"},
                    )
                else:
                    fig_bar = px.bar(
                        df_grouped_month,
                        x=group_col,
                        y="cost",
                        color="category_label",
                        color_discrete_map=CATEGORY_COLOR_MAP,
                        category_orders={group_col: sorted_months},
                        labels={
                            "cost": "Amount (R$)",
                            group_col: "Month",
                            "category_label": "Category",
                        },
                        hover_data={"cost": ":,.2f"},
                    )
                    fig_bar.update_layout(barmode="stack")

                add_total_line_trace(
                    fig_bar,
                    month_totals[group_col],
                    month_totals["cost"],
                    name="Total (Net)",
                    point_labels=not amounts_hidden(),
                )
                fig_bar.add_trace(
                    go.Scatter(
                        x=month_totals[group_col],
                        y=month_totals["moving_avg"],
                        mode="lines",
                        name="3M Moving Avg",
                        line={"color": "#FFB74D", "width": 2, "dash": "dashdot"},
                        opacity=0.85,
                    )
                )

                apply_chart_theme(fig_bar, height=460, legend="top")
                fig_bar.update_layout(
                    xaxis={
                        "type": "category",
                        "categoryorder": "array",
                        "categoryarray": sorted_months,
                        "title": "",
                        "tickangle": -45,
                    },
                    yaxis={"title": "Total (R$)", "range": [0, max_y * 1.3]},
                )
                st.plotly_chart(fig_bar, use_container_width=True)

    with c2:
        with st.container(border=True):
            st.markdown("#### 🏆 Expense Distribution by Category")
            st.markdown(
                f'<span class="hide-amount" style="font-size:0.875rem;opacity:0.6;">'
                f"Total: {format_currency_br(kpis['total_spent'])}</span>",
                unsafe_allow_html=True,
            )
            cat_summary = (
                df_expenses[df_expenses["cost"] > 0]
                .groupby(["category", "category_label"])["cost"]
                .sum()
                .reset_index()
            )

            if not cat_summary.empty:
                fig_cat_bar = build_ranked_bar_chart(
                    cat_summary, "category_label", "cost", color_map=CATEGORY_COLOR_MAP, height=420
                )
                st.plotly_chart(fig_cat_bar, use_container_width=True)

    # ------------------------------------
    # Secondary Charts (Row 2)
    # ------------------------------------
    c3, c4 = st.columns([3, 2])

    with c3:
        with st.container(border=True):
            st.markdown("#### 🏢 Top 10 Merchants / Expenses")
            top_merchants = get_top_merchants(df_expenses, top_n=10)

            if not top_merchants.empty:
                # color each merchant bar with its dominant category's color
                merchant_color_map = (
                    {
                        row["id"]: get_category_color(row["category"])
                        for _, row in top_merchants.iterrows()
                    }
                    if "category" in top_merchants.columns
                    else None
                )
                fig_merchants = build_ranked_bar_chart(
                    top_merchants,
                    "id",
                    "total_spent",
                    color_map=merchant_color_map,
                    height=390,
                )
                st.plotly_chart(fig_merchants, use_container_width=True)

    with c4:
        with st.container(border=True):
            st.markdown("#### 📅 Spending Pattern by Day of Week")
            day_spending = get_day_of_week_spending(df_expenses)

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
                apply_chart_theme(fig_days, height=390, legend="hidden")
                fig_days.update_layout(
                    xaxis={"title": ""},
                    yaxis={"range": [0, max_day_spent * 1.22], "title": "Total (R$)"},
                )
                st.plotly_chart(fig_days, use_container_width=True)
