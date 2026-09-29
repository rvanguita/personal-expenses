import io
from datetime import UTC, datetime

import pandas as pd
from dash import html

from src.expenses.analytics import (
    get_future_installments_details,
    get_future_installments_projection,
    get_next_month_commitment_metrics,
)
from src.expenses.config import format_currency_br
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
from src.expenses.ui.figures import build_budget_vs_limit_figure, build_future_by_category_figure
from src.expenses.ui.insights import executive_summary_insight

DEFAULT_REF_LIMIT = 5000.0


def _installments_label(installment, total) -> str:
    return f"{int(installment)}/{int(total)}" if total > 1 else "Single Payment"


def _forecast_block(df_full: pd.DataFrame, ref_limit: float) -> list:
    metrics = get_next_month_commitment_metrics(df_full, reference_limit=ref_limit)
    projection = get_future_installments_projection(df_full)
    details = get_future_installments_details(df_full)
    if not metrics["has_data"] or projection.empty:
        return [note("No active installment purchases found in the database.")]

    over = metrics["is_over_limit"]
    diff_label = (
        f"+{format_currency_br(metrics['diff_from_limit'])} Over Limit"
        if over
        else f"{format_currency_br(abs(metrics['diff_from_limit']))} Remaining"
    )
    block = [
        card(
            None,
            kpi_row(
                kpi(
                    f"🔒 Next Month ({metrics['next_month']})",
                    format_currency_br(metrics["next_month_cost"]),
                    f"{metrics['num_installments']} active installments billed",
                    diff_label,
                    delta_bad=over,
                ),
                kpi(
                    "🎯 % of Reference Limit",
                    f"{metrics['pct_of_limit']:.1f}%",
                    f"Ref Limit: {format_currency_br(ref_limit)}",
                    "Over Limit!" if over else "Within Safe Budget",
                    delta_bad=over,
                ),
                kpi(
                    "💳 Total Future Installments Debt",
                    format_currency_br(metrics["total_future_debt"]),
                    "Sum of all remaining future installments",
                ),
                kpi(
                    "🗓️ Forecast Horizon",
                    f"{metrics['months_count']} months",
                    f"Until {metrics['max_future_month']}",
                ),
            ),
        ),
        grid(
            card(
                "📊 Monthly Locked Budget vs Reference Line",
                graph(build_budget_vs_limit_figure(projection, ref_limit)),
            ),
            card(
                "🏷️ Future Commitments by Category",
                graph(build_future_by_category_figure(details)),
            ),
        ),
    ]
    if not details.empty:
        display = pd.DataFrame(
            {
                "Billing Month": details["future_month"],
                "Merchant": details["id"],
                "Category": details["category_label"],
                "Purchase Date": pd.to_datetime(details["date_buy"]),
                "Installment": details["installment_display"],
                "Cost": details["cost"].astype(float),
            }
        )
        block.append(
            html.Details(
                [
                    html.Summary("🔍 Detailed List of Upcoming Installments by Purchase"),
                    table(display, money=("Cost",), page_size=20),
                ],
                className="card",
            )
        )
    return block


def export_csv(df_filtered: pd.DataFrame) -> tuple[str, str]:
    """(filename, csv text) for the filtered frame — same format as the Streamlit download."""
    buffer = io.StringIO()
    df_filtered.to_csv(buffer, index=False, sep=";", encoding="utf-8-sig")
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    return f"expenses_report_{stamp}.csv", buffer.getvalue()


def build_reports_view(
    df_filtered: pd.DataFrame, df_full: pd.DataFrame, ref_limit: float | None = None
) -> list:
    if df_filtered.empty:
        return [note("No data selected to generate report.")]
    ref_limit = ref_limit or DEFAULT_REF_LIMIT

    df_exp = df_filtered[~df_filtered["is_payment"]].copy()
    data_table = pd.DataFrame(
        {
            "Invoice Date": pd.to_datetime(df_filtered["date"]),
            "Purchase Date": pd.to_datetime(df_filtered["date_buy"]),
            "Merchant": df_filtered["id"],
            "Category": df_filtered["category_label"],
            "Amount": df_filtered["cost"].astype(float),
            "Installments": [
                _installments_label(i, t)
                for i, t in zip(
                    df_filtered["installment"], df_filtered["total_installments"], strict=True
                )
            ],
        }
    )
    return [
        section("📑 Executive Report & Spending Diagnosis"),
        insight_card(executive_summary_insight(df_exp)),
        section(
            "🔮 Future Installments & Budget Lock Forecast",
            "How much of your future budget is already locked into credit card installments, "
            "compared against the reference limit set above.",
        ),
        *_forecast_block(df_full, ref_limit),
        section("📑 Complete Data Table (Filtered)"),
        card(None, table(data_table, money=("Amount",), page_size=25)),
    ]
