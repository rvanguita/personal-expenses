import pandas as pd
import streamlit as st

from src.expenses.analytics import calculate_kpis
from src.expenses.config import (
    REFERENCE_BUDGET_LIMIT,
    format_currency_br,
    format_currency_md,
)
from src.expenses.ui.figures import (
    CHART_STYLE_LINES,
    CHART_STYLE_STACKED,
    build_category_distribution_figure,
    build_day_of_week_figure,
    build_monthly_evolution_figure,
    build_top_merchants_figure,
)
from src.expenses.ui.insights import automated_insights, health_insight, next_month_insight
from src.expenses.ui.styles import render_insight_card


def _render(insight) -> None:
    if insight is not None:
        render_insight_card(insight.icon, insight.title, insight.message, severity=insight.severity)


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
    _render(health_insight(df_full))

    # ------------------------------------
    # Next Month Installment Commitment Alert
    # ------------------------------------
    _render(next_month_insight(df_full, reference_limit=REFERENCE_BUDGET_LIMIT))

    st.write("")

    # ------------------------------------
    # Automated Insights
    # ------------------------------------
    st.markdown("#### 💡 Automated Insights")
    with st.container(border=True):
        for col, insight in zip(
            st.columns(5), automated_insights(kpis, df_expenses, df_full), strict=True
        ):
            with col:
                _render(insight)

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

            fig_bar = build_monthly_evolution_figure(
                df_expenses,
                group_col=group_col,
                chart_style=(
                    CHART_STYLE_LINES if chart_style == "📈 Trend Lines" else CHART_STYLE_STACKED
                ),
            )
            if fig_bar is not None:
                st.plotly_chart(fig_bar, use_container_width=True)

    with c2:
        with st.container(border=True):
            st.markdown("#### 🏆 Expense Distribution by Category")
            st.markdown(
                f'<span class="hide-amount" style="font-size:0.875rem;opacity:0.6;">'
                f"Total: {format_currency_br(kpis['total_spent'])}</span>",
                unsafe_allow_html=True,
            )
            fig_cat_bar = build_category_distribution_figure(df_expenses)
            if fig_cat_bar is not None:
                st.plotly_chart(fig_cat_bar, use_container_width=True)

    # ------------------------------------
    # Secondary Charts (Row 2)
    # ------------------------------------
    c3, c4 = st.columns([3, 2])

    with c3:
        with st.container(border=True):
            st.markdown("#### 🏢 Top 10 Merchants / Expenses")
            fig_merchants = build_top_merchants_figure(df_expenses, top_n=10)
            if fig_merchants is not None:
                st.plotly_chart(fig_merchants, use_container_width=True)

    with c4:
        with st.container(border=True):
            st.markdown("#### 📅 Spending Pattern by Day of Week")
            fig_days = build_day_of_week_figure(df_expenses, height=390)
            if fig_days is not None:
                st.plotly_chart(fig_days, use_container_width=True)
