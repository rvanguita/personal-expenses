"""Bodies of the secondary tabs: view dict (from `analyses.py`) -> list of Dash components."""

from dash import html

from expenses.config import (
    ANOMALY_Z_THRESHOLD,
    RECURRING_MIN_MONTHS,
    UNCATEGORIZED_WARNING_PCT,
)
from expenses_dash.analyses import FREQUENCY_LABELS, MOMENTUM_LABELS, STATUS_LABELS
from expenses_dash.data import month_label, spend_delta
from expenses_dash.figures import (
    bands_figure,
    category_history_figure,
    comparison_figure,
    heatmap_figure,
    holders_figure,
    limit_figure,
    ranked_bar_figure,
    split_figure,
    weekday_figure,
    yoy_figure,
)
from expenses_dash.fmt import LABEL_TO_KEY, brl, integer, pct
from expenses_dash.layout import card, empty, graph, kpi_row, row, table
from expenses_dash.theme import category_color

NO_ROWS = "No transactions for the selected filters."


# --------------------------------------------------------------------------- Trends


def trends_page(view: dict) -> list:
    if view["is_empty"]:
        return [empty(NO_ROWS)]
    trend, pop = view["trend"], view["pop"]
    period_note = (
        f"{month_label(pop['current_months'][0])}–{month_label(pop['current_months'][-1])}"
        if pop["has_data"]
        else "no previous period"
    )
    cards = [
        {
            "label": "Trend",
            "value": view["direction"],
            "note": f"{brl(trend['slope_per_month'])} per month",
            "help": "Line fitted to the monthly totals of the selected period.",
        },
        {
            "label": "3-month average",
            "value": brl(trend["current_avg"]),
            "note": "last three invoices",
            "help": "Moving average of the three latest invoices in the period.",
        },
        {
            "label": "Next invoice (projected)",
            "value": brl(trend["projected_next"]),
            "note": "extrapolated from the trend",
            "help": "Trend line value for next month.",
        },
        {
            "label": "Period vs previous",
            "value": brl(pop["current_total"]),
            "note": spend_delta(pop["delta_pct"] if pop["has_data"] else None, "vs previous")[0],
            "tone": spend_delta(pop["delta_pct"] if pop["has_data"] else None, "")[1],
            "help": f"Period {period_note} against the same number of months right before it.",
        },
    ]
    momentum = view["momentum"].assign(trend=lambda d: d["direction"].map(MOMENTUM_LABELS))
    return [
        kpi_row(cards),
        card(
            "By category · current vs previous period",
            graph(comparison_figure(pop)),
            note="Top 10 categories in the period against the same number of months before it.",
        ),
        card(
            "Heatmap · category × month",
            graph(heatmap_figure(view["heatmap"])),
            note="Purchases per category on each invoice of the period; brighter = more spend.",
        ),
        row(
            card(
                "Same months · this year vs last year",
                graph(yoy_figure(view["yoy"])),
            ),
            card(
                "Category momentum · last 3 months",
                table(
                    momentum,
                    [
                        ("Category", "category_label", "category"),
                        ("Direction", "trend", "text"),
                        ("Last month", "last_month_value", "money"),
                        ("3-month change", "pct_change_over_window", "pct"),
                    ],
                    max_rows=12,
                ),
            ),
        ),
    ]


# --------------------------------------------------------------------------- Watchlist


def watchlist_page(view: dict) -> list:
    if view["is_empty"]:
        return [empty(NO_ROWS)]
    recurring, anomalies = view["recurring"], view["anomalies"]
    cards = [
        {
            "label": "Fixed monthly cost",
            "value": brl(view["fixed_cost"]),
            "note": f"≈ {brl(view['fixed_cost'] * 12)} per year",
            "help": "Sum of the monthly average of recurring charges.",
        },
        {
            "label": "Recurring charges",
            "value": str(len(recurring)),
            "note": f"billed in {RECURRING_MIN_MONTHS}+ months at a stable amount",
            "help": "Subscriptions, insurance, memberships — full history.",
        },
        {
            "label": "Unusual purchases",
            "value": str(len(anomalies)),
            "note": f"more than {ANOMALY_Z_THRESHOLD}σ above their category",
            "help": "Purchases far above the typical amount for their category, in the period.",
        },
        {
            "label": "Uncategorized",
            "value": brl(view["uncategorized_total"]),
            "note": f"{pct(view['uncategorized_pct'])} of spend in the period",
            "tone": "bad" if view["uncategorized_pct"] > UNCATEGORIZED_WARNING_PCT else "neutral",
            "help": "Classify these merchants in the Streamlit Categorize tab.",
        },
    ]
    recurring = recurring.assign(
        status_label=lambda d: d["status"].map(STATUS_LABELS),
        category=lambda d: d["category_label"].map(_label_to_key),
    )
    anomalies = anomalies.assign(z=lambda d: d["z_score"].map(lambda z: f"{z:.1f}σ"))
    frequency = view["frequency"].assign(
        direction_label=lambda d: d["direction"].map(FREQUENCY_LABELS)
    )
    return [
        kpi_row(cards),
        card(
            "Recurring charges",
            table(
                recurring,
                [
                    ("Merchant", "id", "text"),
                    ("Category", "category_label", "category"),
                    ("Avg / month", "avg_monthly_cost", "money"),
                    ("Last charge", "last_amount", "money"),
                    ("Month", "last_month", "month"),
                    ("Months", "months_count", "int"),
                    ("Status", "status_label", "text"),
                ],
            )
            if not recurring.empty
            else empty("No recurring charges detected."),
        ),
        row(
            card(
                "Unusual purchases",
                table(
                    anomalies,
                    [
                        ("Date", "date_buy", "date"),
                        ("Merchant", "id", "text"),
                        ("Category", "category_label", "category"),
                        ("Amount", "cost", "money"),
                        ("Category avg", "category_avg", "money"),
                        ("Deviation", "z", "text"),
                    ],
                    max_rows=15,
                )
                if not anomalies.empty
                else empty("Nothing unusual in the period."),
            ),
            card(
                "Uncategorized",
                table(
                    view["uncategorized"],
                    [
                        ("Merchant", "id", "text"),
                        ("Purchases", "tx", "int"),
                        ("Total", "total", "money"),
                        ("Last purchase", "last", "date"),
                    ],
                    max_rows=15,
                )
                if not view["uncategorized"].empty
                else empty("Everything in the period has a category."),
            ),
        ),
        card(
            "New merchants in the period",
            table(
                view["new_merchants"],
                [
                    ("Merchant", "id", "text"),
                    ("Category", "category_label", "category"),
                    ("First purchase", "first", "date"),
                    ("Purchases", "tx", "int"),
                    ("Total", "total", "money"),
                ],
                max_rows=15,
            )
            if not view["new_merchants"].empty
            else empty("No new merchants (or the period starts at the beginning of the history)."),
            note="Their first purchase in the whole history falls inside the selected period.",
        ),
        card(
            "Frequency changes",
            table(
                frequency,
                [
                    ("Merchant", "id", "text"),
                    ("Category", "category_label", "text"),
                    ("Recent (purchases/month)", "recent_monthly_rate", "rate"),
                    ("Baseline (purchases/month)", "baseline_monthly_rate", "rate"),
                    ("Change", "change_pct", "pct"),
                    ("", "direction_label", "text"),
                ],
                max_rows=15,
            )
            if not frequency.empty
            else empty("Not enough history to compare frequency."),
            note="Last 2 months against the 6 before them; changes above 50%.",
        ),
    ]


def _label_to_key(label: str) -> str:
    return LABEL_TO_KEY.get(label, "not_found")


# --------------------------------------------------------------------------- Categories


def category_page(view: dict) -> list:
    if view["is_empty"]:
        return [empty(NO_ROWS)]
    key = view["selected"]
    cards = [
        {
            "label": "Total",
            "value": brl(view["total"]),
            "note": spend_delta(view["momentum_pct"], "over 3 months")[0],
            "tone": spend_delta(view["momentum_pct"], "")[1],
            "help": "Change compares the latest month with three months earlier.",
        },
        {
            "label": "Share of spend",
            "value": pct(view["share_pct"]),
            "note": "of spend in the period",
            "help": "Share of the period's spend (positive purchases) in this category.",
        },
        {
            "label": "Purchases",
            "value": integer(view["count"]),
            "note": view["label"],
            "help": "Number of purchases in this category in the period.",
        },
        {
            "label": "Average ticket",
            "value": brl(view["avg_ticket"]),
            "note": "per purchase",
            "help": "Category total divided by the number of purchases.",
        },
    ]
    merchants = view["merchants"]
    largest = view["largest"].assign(
        installments_label=lambda d: [
            f"{int(i)}/{int(t)}" if t > 1 else "Single payment"
            for i, t in zip(d["installment"], d["total_installments"], strict=True)
        ]
    )
    return [
        kpi_row(cards),
        row(
            card("Monthly history", graph(category_history_figure(view["history"], key))),
            card(
                "Top merchants",
                graph(
                    ranked_bar_figure(
                        merchants, "id", "cost", [category_color(key)] * len(merchants), height=320
                    )
                ),
            ),
        ),
        card(
            "Largest purchases",
            table(
                largest,
                [
                    ("Date", "date_buy", "date"),
                    ("Merchant", "id", "text"),
                    ("Installments", "installments_label", "text"),
                    ("Amount", "cost", "money"),
                ],
            ),
        ),
    ]


# --------------------------------------------------------------------------- Reports


def reports_page(view: dict) -> list:
    metrics, limit = view["metrics"], view["limit"]
    if metrics["has_data"]:
        over = metrics["is_over_limit"]
        diff = brl(abs(metrics["diff_from_limit"]))
        cards = [
            {
                "label": f"Installments {month_label(metrics['next_month'])}",
                "value": brl(metrics["next_month_cost"]),
                "note": f"{diff} over the limit" if over else f"{diff} left within the limit",
                "tone": "bad" if over else "good",
                "help": f"{metrics['num_installments']} installments already due on the next invoice.",
            },
            {
                "label": "Limit used",
                "value": pct(metrics["pct_of_limit"], 0),
                "note": f"of a {brl(limit)} limit",
                "help": "Set by REFERENCE_BUDGET_LIMIT in .env.",
            },
            {
                "label": "Total left in installments",
                "value": brl(metrics["total_future_debt"]),
                "note": f"over {metrics['months_count']} months",
                "help": f"Last installment in {month_label(metrics['max_future_month'])}.",
            },
            {
                "label": "Transactions in selection",
                "value": integer(view["rows"]),
                "note": "exportable as CSV below",
                "help": "Rows for the current period and filters (invoice payments excluded).",
            },
        ]
        commitments = [
            kpi_row(cards),
            row(
                card(
                    "Installments per month vs limit",
                    graph(limit_figure(view["projection"], limit)),
                ),
                card(
                    "Upcoming installments",
                    html_scroll(
                        table(
                            view["details"],
                            [
                                ("Invoice", "future_month", "month"),
                                ("Merchant", "id", "text"),
                                ("Installment", "installment_display", "text"),
                                ("Amount", "cost", "money"),
                            ],
                        )
                    ),
                ),
            ),
        ]
    else:
        commitments = [card("Installments", empty("No open installment purchases."))]

    invoices = (
        table(
            view["invoices"],
            [
                ("Invoice", "year_month", "month"),
                ("Purchases", "tx", "int"),
                ("Gross", "gross", "money"),
                ("Refunds", "refunds", "money"),
                ("Net", "net", "money"),
            ],
        )
        if not view["invoices"].empty
        else empty(NO_ROWS)
    )
    return [*commitments, card("Invoice totals", invoices)]


def html_scroll(child) -> html.Div:
    return html.Div(child, className="pe-scroll")


# --------------------------------------------------------------------------- Habits


def habits_page(view: dict) -> list:
    if view["is_empty"]:
        return [empty(NO_ROWS)]
    cards = [
        {
            "label": "Purchases per month",
            "value": f"{view['per_month']:.0f}",
            "note": f"{integer(view['count'])} purchases in the period",
            "help": "Number of purchases (refunds excluded) divided by the number of invoices.",
        },
        {
            "label": "Average ticket",
            "value": brl(view["avg_ticket"]),
            "note": f"median {brl(view['median_ticket'])}",
            "help": "Mean and median amount per purchase; a median well below the mean means a "
            "few large purchases pull the total up.",
        },
        {
            "label": "In installments",
            "value": pct(view["installment_share"]),
            "note": "of purchase value",
            "help": "Share of the period's purchase value paid in installments.",
        },
        {
            "label": "Concentration",
            "value": pct(view["top10_share"]),
            "note": f"in the top 10 · {view['pareto_n']} of {view['merchants']} make 80%",
            "help": "How much of the spend sits in the 10 largest merchants, and how many "
            "merchants add up to 80% of it.",
        },
    ]
    return [
        kpi_row(cards),
        row(
            card(
                "Single payment vs installments",
                graph(split_figure(view["split"])),
                note="Purchase value per invoice, split by payment method.",
            ),
            card(
                "Ticket size bands",
                graph(bands_figure(view["bands"])),
                note="How much of the spend comes from small, medium and large purchases.",
            ),
        ),
        row(
            card(
                "Day of week",
                graph(weekday_figure(view["weekday"])),
                note="By purchase date; the highest-spend day is highlighted.",
            ),
            card(
                "By cardholder",
                graph(holders_figure(view["holders"])),
                note="Purchases by each cardholder per invoice.",
            ),
        ),
    ]
