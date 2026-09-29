import pandas as pd
from dash import html

from src.expenses.analytics import get_category_momentum
from src.expenses.config import CATEGORY_CONFIG, DAY_OF_WEEK_LABELS_PT, format_currency_br
from src.expenses.dash_ui.components import (
    card,
    graph,
    grid,
    insight_card,
    kpi,
    kpi_row,
    note,
    section,
    table,
)
from src.expenses.ui.charts import build_ranked_bar_chart
from src.expenses.ui.figures import build_category_monthly_figure, build_day_of_week_figure
from src.expenses.ui.insights import category_momentum_insight

DOW_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def category_options(df_filtered: pd.DataFrame) -> list[dict]:
    """Dropdown options for the deep-dive selector; ``not_found`` is listed last."""
    cats = [c for c in sorted(df_filtered["category"].unique()) if c in CATEGORY_CONFIG]
    if "not_found" in cats:
        cats.remove("not_found")
        cats.append("not_found")
    return [
        {"label": f"{CATEGORY_CONFIG[c]['icon']} {CATEGORY_CONFIG[c]['label']}", "value": c}
        for c in cats
    ]


def _uncategorized_block(df_filtered: pd.DataFrame) -> list:
    nf = df_filtered[(df_filtered["category"] == "not_found") & (df_filtered["cost"] > 0)]
    if nf.empty:
        return []
    total_exp = float(df_filtered[df_filtered["cost"] > 0]["cost"].sum())
    nf_total = float(nf["cost"].sum())
    share = (nf_total / total_exp * 100) if total_exp > 0 else 0.0

    top_merchants = (
        nf.groupby("id")["cost"]
        .sum()
        .reset_index()
        .sort_values(by="cost", ascending=False)
        .head(5)
        .rename(columns={"id": "Merchant", "cost": "Total Amount"})
    )
    latest = nf.sort_values(by="date_buy", ascending=False).head(5)
    latest_display = pd.DataFrame(
        {
            "Purchase Date": pd.to_datetime(latest["date_buy"]),
            "Merchant": latest["id"],
            "Amount": latest["cost"].astype(float),
        }
    )
    return [
        html.Details(
            [
                html.Summary(
                    f"⚠️ ❓ Uncategorized Expenses (not_found): {format_currency_br(nf_total)} "
                    f"({len(nf)} transactions, {share:.1f}% of total)"
                ),
                note(
                    "These transactions have no assigned category. Classify them with Gemini AI in "
                    "the Streamlit app's AI Categorization tab."
                ),
                kpi_row(
                    kpi("Uncategorized Total", format_currency_br(nf_total)),
                    kpi("Pending Transactions", f"{len(nf):,}"),
                    kpi("Share of Spending", f"{share:.1f}%"),
                ),
                grid(
                    html.Div(
                        [
                            html.H5("Top Uncategorized Merchants"),
                            table(top_merchants, money=("Total Amount",)),
                        ]
                    ),
                    html.Div(
                        [
                            html.H5("Latest Uncategorized Items"),
                            table(latest_display, money=("Amount",)),
                        ]
                    ),
                ),
            ],
            open=True,
            className="card",
        )
    ]


def _day_of_week_table(df_cat_exp: pd.DataFrame, cat_total: float) -> pd.DataFrame:
    agg = (
        df_cat_exp.assign(day_name=df_cat_exp["date_buy"].dt.day_name())
        .groupby("day_name")
        .agg(total_sum=("cost", "sum"), tx_count=("cost", "count"))
        .reindex(DOW_ORDER)
        .fillna(0.0)
        .reset_index()
    )
    agg["avg_ticket"] = (agg["total_sum"] / agg["tx_count"].where(agg["tx_count"] > 0)).fillna(0.0)
    agg["share_pct"] = agg["total_sum"] / cat_total * 100 if cat_total > 0 else 0.0
    return agg


def build_category_view(df_filtered: pd.DataFrame, selected_cat: str | None) -> list:
    if df_filtered.empty:
        return [note("No transactions to analyze.")]

    view = [section("🔍 Category Breakdown & Analysis"), *_uncategorized_block(df_filtered)]
    if selected_cat not in CATEGORY_CONFIG or selected_cat not in set(df_filtered["category"]):
        return [*view, note("Select a category to analyze in detail.")]

    meta = CATEGORY_CONFIG[selected_cat]
    df_cat_exp = df_filtered[(df_filtered["category"] == selected_cat) & (df_filtered["cost"] > 0)]
    df_cat_exp = df_cat_exp.copy()
    cat_total = float(df_cat_exp["cost"].sum())
    cat_count = len(df_cat_exp)
    global_exp = float(df_filtered[df_filtered["cost"] > 0]["cost"].sum())

    momentum = get_category_momentum(df_filtered, window=3)
    momentum_row = momentum[momentum["category"] == selected_cat]
    if not momentum_row.empty:
        view.append(insight_card(category_momentum_insight(momentum_row.iloc[0], meta["label"])))

    peak_date, peak_date_val = "N/A", 0.0
    if not df_cat_exp.empty:
        daily = df_cat_exp.groupby(df_cat_exp["date_buy"].dt.date)["cost"].sum()
        peak_date = pd.to_datetime(daily.idxmax()).strftime("%d/%m/%Y")
        peak_date_val = float(daily.max())
    dow = _day_of_week_table(df_cat_exp, cat_total)
    peak_dow_row = dow.loc[dow["total_sum"].idxmax()]
    has_dow = peak_dow_row["total_sum"] > 0

    view += [
        section("📊 Category KPIs"),
        card(
            None,
            kpi_row(
                kpi("Category Total", format_currency_br(cat_total)),
                kpi("Transactions", f"{cat_count:,}"),
                kpi("Avg Ticket", format_currency_br(cat_total / cat_count if cat_count else 0.0)),
                kpi("Global Share", f"{(cat_total / global_exp * 100) if global_exp else 0:.1f}%"),
                kpi("Peak Day (Date)", peak_date, delta=format_currency_br(peak_date_val)),
                kpi(
                    "Peak Day of Week",
                    str(peak_dow_row["day_name"]) if has_dow else "N/A",
                    delta=format_currency_br(float(peak_dow_row["total_sum"]) if has_dow else 0.0),
                ),
            ),
        ),
    ]

    cat_merchants = (
        df_cat_exp.groupby("id")["cost"]
        .sum()
        .reset_index()
        .sort_values(by="cost", ascending=False)
        .head(7)
    )
    view.append(
        grid(
            card(
                f"Monthly History: {meta['label']}",
                graph(build_category_monthly_figure(df_cat_exp, meta["label"], meta["color"])),
            ),
            card(
                "Top Merchants in Category",
                graph(
                    build_ranked_bar_chart(cat_merchants, "id", "cost", height=340)
                    if not cat_merchants.empty
                    else None
                ),
            ),
            columns="3fr 2fr",
        )
    )

    dow_cards = [
        kpi(
            f"{d[:3]} ({DAY_OF_WEEK_LABELS_PT[d][:3]})",
            format_currency_br(float(r["total_sum"])),
            delta=f"{int(r['tx_count'])} tx ({r['share_pct']:.1f}%)",
        )
        for d, (_, r) in zip(DOW_ORDER, dow.iterrows(), strict=True)
    ]
    dow_table = pd.DataFrame(
        {
            "Day of Week": dow["day_name"].map(lambda d: f"{d} ({DAY_OF_WEEK_LABELS_PT[d]})"),
            "Total Spent": dow["total_sum"].astype(float),
            "Transactions": dow["tx_count"].astype(int),
            "Avg Ticket": dow["avg_ticket"].astype(float),
            "% Share": dow["share_pct"].astype(float),
        }
    )
    view += [
        section(f"📅 Spending Pattern by Day of Week: {meta['label']}"),
        card(None, kpi_row(*dow_cards)),
        grid(
            card(
                "📊 Chart",
                graph(build_day_of_week_figure(df_cat_exp, height=340, headroom=1.25)),
            ),
            card(
                "📋 Breakdown",
                table(
                    dow_table,
                    money=("Total Spent", "Avg Ticket"),
                    integer=("Transactions",),
                    percent=("% Share",),
                    page_size=7,
                ),
            ),
            columns="3fr 2fr",
        ),
    ]

    top_tx = df_cat_exp.sort_values(by="cost", ascending=False).head(15)
    top_display = pd.DataFrame(
        {
            "Invoice Date": pd.to_datetime(top_tx["date"]),
            "Purchase Date": pd.to_datetime(top_tx["date_buy"]),
            "Merchant": top_tx["id"],
            "Amount": top_tx["cost"].astype(float),
            "Installments": [
                f"{int(i)}/{int(t)}" if t > 1 else "Single Payment"
                for i, t in zip(top_tx["installment"], top_tx["total_installments"], strict=True)
            ],
        }
    )
    view += [
        section("📋 Largest Transactions in this Category"),
        card(None, table(top_display, money=("Amount",))),
    ]
    return view
