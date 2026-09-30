"""Framework-agnostic narrative insights (icon / title / markdown message / severity).

Frontends render an ``Insight`` however they like (e.g. Streamlit ``render_insight``). Messages
are markdown; currency uses ``format_currency_md`` so ``$`` is pre-escaped.
"""

from dataclasses import dataclass

import pandas as pd

from expenses.analytics import (
    get_month_pace_projection,
    get_next_month_commitment_metrics,
    get_spending_anomalies,
)
from expenses.config import (
    ANOMALY_MIN_CATEGORY_TX,
    ANOMALY_Z_THRESHOLD,
    INSTALLMENT_BURDEN_WARNING_PCT,
    REFERENCE_BUDGET_LIMIT,
    UNCATEGORIZED_WARNING_PCT,
    format_currency_md,
)

# Severities that ask the user to act, most urgent first.
ATTENTION_SEVERITIES = ("critical", "warning")


@dataclass(frozen=True)
class Insight:
    icon: str
    title: str
    message: str
    severity: str = "info"


def next_month_insight(
    df_full: pd.DataFrame, reference_limit: float = REFERENCE_BUDGET_LIMIT
) -> Insight | None:
    m = get_next_month_commitment_metrics(df_full, reference_limit=reference_limit)
    if not m["has_data"]:
        return None
    cost = format_currency_md(m["next_month_cost"])
    diff = format_currency_md(abs(m["diff_from_limit"]))
    if m["is_over_limit"]:
        return Insight(
            "⚠️",
            f"{m['next_month']} is over budget",
            f"**{cost}** already committed in installments — **{diff}** above the "
            f"{format_currency_md(reference_limit)} limit.",
            "critical",
        )
    return Insight(
        "🔒",
        f"{m['next_month']} budget on track",
        f"**{cost}** committed in installments; **{diff}** left under the limit.",
        "good",
    )


def _installment_insight(kpis: dict) -> Insight:
    pct = kpis["installment_pct"]
    if pct > INSTALLMENT_BURDEN_WARNING_PCT:
        return Insight(
            "💳",
            "High installment share",
            f"**{pct:.1f}%** of spending is in installments "
            f"(alert above {INSTALLMENT_BURDEN_WARNING_PCT:.0f}%).",
            "warning",
        )
    return Insight(
        "💳", "Installment share", f"**{pct:.1f}%** of spending is in installments.", "good"
    )


def _anomaly_summary_insight(df_expenses: pd.DataFrame) -> Insight:
    anomalies = get_spending_anomalies(
        df_expenses, z_threshold=ANOMALY_Z_THRESHOLD, min_category_tx=ANOMALY_MIN_CATEGORY_TX
    )
    if anomalies.empty:
        return Insight("✅", "No unusual purchases", "Nothing stands out.", "good")
    return Insight(
        "🔎",
        f"{len(anomalies)} unusual purchase(s)",
        "Well above their category's typical amount. Review them in **Watchlist**.",
        "warning",
    )


def _pace_insight(df_full: pd.DataFrame) -> Insight:
    pace = get_month_pace_projection(df_full)
    if not pace["has_data"]:
        return Insight("📆", "Spending pace", "Not enough data to project this month.", "info")
    projected = format_currency_md(pace["projected_total"])
    if pace["status"] == "hot":
        return Insight(
            "🔥",
            "Spending pace is high",
            f"**{pace['current_month']}** is heading to **{projected}** "
            f"({pace['pace_delta_pct']:+.1f}% vs recent average).",
            "warning",
        )
    return Insight(
        "📆",
        "Spending pace",
        f"**{pace['current_month']}** is projected at **{projected}**.",
        "good" if pace["status"] == "cold" else "info",
    )


def uncategorized_insight(df_expenses: pd.DataFrame) -> Insight | None:
    """Warns when uncategorized purchases exceed ``UNCATEGORIZED_WARNING_PCT`` of spending."""
    positive = df_expenses[df_expenses["cost"] > 0]
    total = float(positive["cost"].sum())
    nf = positive[positive["category"] == "not_found"]
    if nf.empty or total <= 0:
        return None
    nf_total = float(nf["cost"].sum())
    pct = nf_total / total * 100
    if pct <= UNCATEGORIZED_WARNING_PCT:
        return None
    return Insight(
        "❓",
        "Uncategorized spending",
        f"**{format_currency_md(nf_total)}** ({pct:.1f}%) has no category. "
        "Classify it in **Categorize**.",
        "warning",
    )


def attention_insights(
    kpis: dict,
    df_expenses: pd.DataFrame,
    df_full: pd.DataFrame,
    reference_limit: float = REFERENCE_BUDGET_LIMIT,
    limit: int = 3,
) -> list[Insight]:
    """Only the insights that ask for action (critical first), capped at ``limit``."""
    candidates = [
        next_month_insight(df_full, reference_limit=reference_limit),
        _installment_insight(kpis),
        _pace_insight(df_full),
        _anomaly_summary_insight(df_expenses),
        uncategorized_insight(df_expenses),
    ]
    flagged = [i for i in candidates if i is not None and i.severity in ATTENTION_SEVERITIES]
    flagged.sort(key=lambda i: ATTENTION_SEVERITIES.index(i.severity))
    return flagged[:limit]
