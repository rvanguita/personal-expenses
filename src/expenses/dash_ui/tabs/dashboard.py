import pandas as pd
from dash import html

from src.expenses.analytics import calculate_kpis
from src.expenses.config import REFERENCE_BUDGET_LIMIT, format_currency_br
from src.expenses.dash_ui.components import (
    card,
    graph,
    grid,
    insight_cards,
    kpi,
    kpi_row,
    note,
    section,
    table,
)
from src.expenses.ui.figures import (
    build_category_distribution_figure,
    build_day_of_week_figure,
    build_monthly_evolution_figure,
    build_top_merchants_figure,
)
from src.expenses.ui.insights import automated_insights, health_insight, next_month_insight


def _invoice_summary(df_expenses: pd.DataFrame) -> pd.DataFrame:
    summary = (
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
    return pd.DataFrame(
        {
            "Invoice Month": summary["year_month"],
            "Invoice Date": pd.to_datetime(summary["date"]),
            "Transactions": summary["tx_count"].astype(int),
            "Gross Purchases": summary["gross_cost"].astype(float),
            "Refunds / Estornos": summary["refunds"].astype(float),
            "Net Invoice Total": summary["net_cost"].astype(float),
        }
    )


def build_dashboard_view(
    df_filtered: pd.DataFrame,
    df_full: pd.DataFrame,
    *,
    group_col: str = "year_month",
    chart_style: str = "stacked",
) -> list:
    if df_filtered.empty:
        return [note("No transactions found with the selected filters.")]

    df_expenses = df_filtered[~df_filtered["is_payment"]].copy()
    kpis = calculate_kpis(df_filtered, df_full)

    banners = insight_cards(
        [
            health_insight(df_full),
            next_month_insight(df_full, reference_limit=REFERENCE_BUDGET_LIMIT),
        ]
    )

    refunds_caption = (
        f"Gross: {format_currency_br(kpis['gross_spent'])} | Refunds: "
        f"{format_currency_br(kpis['total_refunds'])}"
        if kpis["total_refunds"] < 0
        else f"Invoices: {kpis['num_months']} selected"
    )
    delta = f"{kpis['mom_delta_pct']:+.1f}% ({format_currency_br(kpis['mom_delta_val'])})"
    kpi_tiles = kpi_row(
        kpi("💰 Net Spent", format_currency_br(kpis["total_spent"]), refunds_caption),
        kpi("📅 Monthly Avg", format_currency_br(kpis["avg_monthly_spent"]), "Avg net per invoice"),
        kpi(
            "📈 MoM Variation",
            format_currency_br(kpis["latest_m_val"]),
            "Latest vs previous",
            delta,
            delta_bad=(kpis["mom_delta_pct"] > 0) if kpis["mom_delta_pct"] else None,
        ),
        kpi(
            "🏆 Top Category",
            kpis["top_cat_name"],
            f"{format_currency_br(kpis['top_cat_val'])} ({kpis['top_cat_pct']:.1f}%)",
        ),
        kpi(
            "🧾 Transactions",
            f"{kpis['total_tx']:,}",
            f"Avg Ticket: {format_currency_br(kpis['avg_tx'])}",
        ),
        kpi(
            "💳 Installments",
            f"{kpis['installment_pct']:.1f}%",
            f"{format_currency_br(kpis['installment_spent'])} total",
        ),
    )

    return [
        *banners,
        section("💡 Automated Insights"),
        card(
            None,
            html.Div(
                insight_cards(automated_insights(kpis, df_expenses, df_full)),
                className="insight-row",
            ),
        ),
        section("📊 Key Performance Indicators"),
        card(None, kpi_tiles),
        html.Details(
            [
                html.Summary("📋 Detailed Monthly Invoice Totals (Grouped by Invoice date)"),
                table(
                    _invoice_summary(df_expenses),
                    money=("Gross Purchases", "Refunds / Estornos", "Net Invoice Total"),
                    integer=("Transactions",),
                ),
            ],
            className="card",
        ),
        grid(
            card(
                "📊 Monthly Expense Evolution by Category",
                graph(
                    build_monthly_evolution_figure(
                        df_expenses, group_col=group_col, chart_style=chart_style
                    )
                ),
            ),
            card(
                "🏆 Expense Distribution by Category",
                html.Div(
                    f"Total: {format_currency_br(kpis['total_spent'])}", className="note money"
                ),
                graph(build_category_distribution_figure(df_expenses)),
            ),
            columns="3fr 2fr",
        ),
        grid(
            card("🏢 Top 10 Merchants / Expenses", graph(build_top_merchants_figure(df_expenses))),
            card(
                "📅 Spending Pattern by Day of Week", graph(build_day_of_week_figure(df_expenses))
            ),
            columns="3fr 2fr",
        ),
    ]
