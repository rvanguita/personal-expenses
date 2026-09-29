import pandas as pd

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
from src.expenses.dash_ui.components import (
    card,
    graph,
    insight_card,
    kpi,
    kpi_row,
    note,
    section,
    table,
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

_MOMENTUM_ICONS = {"rising": "▲", "falling": "▼", "stable": "→"}
_DIRECTION_LABEL = {"up": "📈 Rising", "down": "📉 Falling", "stable": "⚖️ Stable"}


def _trend_block(df_expenses: pd.DataFrame) -> list:
    trend = get_spending_trend(df_expenses, group_col="year_month")
    if not trend["has_data"]:
        return [note("Not enough monthly data yet to compute a spending trend.")]
    return [
        card(
            None,
            kpi_row(
                kpi(
                    "Trend Direction",
                    _DIRECTION_LABEL[trend["direction"]],
                    "Based on a linear regression over the visible period",
                ),
                kpi(
                    "3-Month Moving Average",
                    format_currency_br(trend["current_avg"]),
                    "Smoothed recent spending level",
                ),
                kpi(
                    "Projected Next Month",
                    format_currency_br(trend["projected_next"]),
                    "Simple trend-line projection",
                ),
            ),
            graph(build_trend_figure(trend["moving_avg_df"]), "Not enough months to plot."),
        )
    ]


def _period_block(df_filtered: pd.DataFrame, df_full: pd.DataFrame) -> list:
    selected_months = sorted(df_filtered["year_month"].dropna().unique().tolist())
    pop = get_period_over_period_comparison(df_full, selected_months)
    if not pop["has_data"]:
        return [
            note("Not enough historical data before the selected period to build a comparison.")
        ]
    cur, prev = pop["current_months"], pop["previous_months"]
    return [
        card(
            None,
            kpi_row(
                kpi(
                    f"Current Period ({len(cur)} mo.)",
                    format_currency_br(pop["current_total"]),
                    f"{cur[0]} → {cur[-1]}",
                ),
                kpi(
                    f"Previous Period ({len(prev)} mo.)",
                    format_currency_br(pop["previous_total"]),
                    f"{prev[0]} → {prev[-1]}",
                ),
                kpi(
                    "Variation",
                    format_currency_br(pop["delta"]),
                    "Current vs previous period",
                    f"{pop['delta_pct']:+.1f}%",
                    delta_bad=pop["delta"] > 0 if pop["delta"] else None,
                ),
            ),
            graph(build_period_comparison_figure(pop)),
        )
    ]


def _momentum_block(df_full: pd.DataFrame) -> list:
    momentum = get_category_momentum(df_full, window=3)
    if momentum.empty:
        return [
            note(
                "Not enough monthly history yet to compute category momentum "
                "(needs 3+ months of data per category)."
            )
        ]
    display = pd.DataFrame(
        {
            "Category": momentum["category_label"],
            "Trend": momentum["direction"].apply(
                lambda d: f"{_MOMENTUM_ICONS.get(d, '→')} {d.title()}"
            ),
            "Last Month": momentum["last_month_value"].astype(float),
            "3-Month Change (%)": momentum["pct_change_over_window"].astype(float),
        }
    )
    return [
        card(
            None,
            insight_card(top_momentum_insight(momentum)),
            table(display, money=("Last Month",), percent=("3-Month Change (%)",)),
        )
    ]


def _yoy_block(df_full: pd.DataFrame) -> list:
    yoy = get_year_over_year_comparison(df_full)
    if yoy.empty:
        return [note("Year-over-Year comparison needs at least two years of invoice history.")]
    cur_year = int(yoy["current_year"].iloc[0])
    prev_year = int(yoy["previous_year"].iloc[0])
    total_cur = float(yoy["current_val"].sum())
    total_prev = float(yoy["previous_val"].sum())
    delta_pct = ((total_cur - total_prev) / total_prev * 100) if total_prev else 0.0
    return [
        card(
            None,
            kpi_row(
                kpi(
                    f"{cur_year} (Current)",
                    format_currency_br(total_cur),
                    f"Across {len(yoy)} overlapping month(s)",
                ),
                kpi(
                    f"{prev_year} (Previous)",
                    format_currency_br(total_prev),
                    "Same months, prior year",
                ),
                kpi(
                    "Variation",
                    format_currency_br(total_cur - total_prev),
                    "Year-over-year",
                    f"{delta_pct:+.1f}%",
                    delta_bad=total_cur > total_prev if total_cur != total_prev else None,
                ),
            ),
            graph(build_yoy_figure(yoy)),
        )
    ]


def _recurring_block(df_full: pd.DataFrame) -> list:
    recurring = get_recurring_merchants(
        df_full, min_months=RECURRING_MIN_MONTHS, max_cv=RECURRING_MAX_CV
    )
    if recurring.empty:
        return [
            note(
                "No recurring subscription-like merchants detected yet "
                "(needs at least 3 months of consistent billing history)."
            )
        ]
    total = float(recurring["avg_monthly_cost"].sum())
    display = pd.DataFrame(
        {
            "Merchant": recurring["id"],
            "Category": recurring["category_label"],
            "Months Active": recurring["months_count"],
            "Avg Monthly Cost": recurring["avg_monthly_cost"],
            "Last Billed": recurring["last_amount"],
            "Last Month": recurring["last_month"],
            "Status": recurring["status"].map(
                {"Increased": "🔺 Increased", "Decreased": "🔻 Decreased", "Stable": "✅ Stable"}
            ),
        }
    )
    return [
        card(
            None,
            kpi_row(
                kpi("Estimated Monthly Fixed Cost", format_currency_br(total)),
                kpi("Recurring Merchants Detected", f"{len(recurring)}"),
                kpi("Estimated Annual Impact", format_currency_br(total * 12)),
            ),
            table(display, money=("Avg Monthly Cost", "Last Billed"), integer=("Months Active",)),
        )
    ]


def _frequency_block(df_full: pd.DataFrame) -> list:
    freq = get_merchant_frequency_change(df_full)
    if freq.empty:
        return [
            note(
                "No notable merchant frequency changes detected yet "
                "(needs enough purchase history to establish a baseline)."
            )
        ]
    display = pd.DataFrame(
        {
            "Merchant": freq["id"],
            "Category": freq["category_label"],
            "Recent Rate (tx/mo)": freq["recent_monthly_rate"].astype(float),
            "Baseline Rate (tx/mo)": freq["baseline_monthly_rate"].astype(float),
            "Change": freq["direction"].map(
                {"increased": "🔺 Increased", "decreased": "🔻 Decreased"}
            ),
            "Change (%)": freq["change_pct"].astype(float),
        }
    )
    return [
        card(
            None,
            insight_card(frequency_change_insight(freq)),
            table(
                display,
                percent=("Recent Rate (tx/mo)", "Baseline Rate (tx/mo)", "Change (%)"),
            ),
        )
    ]


def _anomalies_block(df_expenses: pd.DataFrame) -> list:
    anomalies = get_spending_anomalies(
        df_expenses, z_threshold=ANOMALY_Z_THRESHOLD, min_category_tx=ANOMALY_MIN_CATEGORY_TX
    )
    children = [insight_card(anomalies_insight(anomalies))]
    if not anomalies.empty:
        display = pd.DataFrame(
            {
                "Purchase Date": pd.to_datetime(anomalies["date_buy"]),
                "Merchant": anomalies["id"],
                "Category": anomalies["category_label"],
                "Amount": anomalies["cost"].astype(float),
                "Category Avg": anomalies["category_avg"].astype(float),
                "Deviation": anomalies["z_score"].apply(lambda z: f"{z:.1f}σ above average"),
            }
        )
        children.append(table(display, money=("Amount", "Category Avg")))
    return [card(None, *children)]


def build_trends_view(df_filtered: pd.DataFrame, df_full: pd.DataFrame) -> list:
    if df_filtered.empty:
        return [note("No transactions found with the selected filters.")]
    df_expenses = df_filtered[~df_filtered["is_payment"]].copy()
    return [
        section("📈 Trends, Comparisons & Anomaly Detection"),
        section("🔮 Spending Trend & Next Month Forecast"),
        *_trend_block(df_expenses),
        section(
            "⏮️ Period-over-Period Comparison",
            "Compares the currently selected invoices against the immediately preceding period "
            "of equal length.",
        ),
        *_period_block(df_filtered, df_full),
        section(
            "🧭 Category Momentum (3-Month Trend)",
            "Categories with a consistent rising or falling trend across the last 3 months.",
        ),
        *_momentum_block(df_full),
        section("📆 Year-over-Year Comparison"),
        *_yoy_block(df_full),
        section(
            "🔁 Recurring Subscriptions & Fixed Costs",
            "Merchants billed consistently across multiple months, detected from amount stability.",
        ),
        *_recurring_block(df_full),
        section(
            "🔀 Merchant Frequency Change",
            "Merchants whose recent buying frequency shifted notably from their historical baseline.",
        ),
        *_frequency_block(df_full),
        section(
            "⚠️ Unusual Transactions Detected",
            "Purchases significantly above the typical spending pattern for their category.",
        ),
        *_anomalies_block(df_expenses),
    ]
