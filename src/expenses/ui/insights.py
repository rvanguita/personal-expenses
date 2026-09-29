"""Framework-agnostic narrative insights (icon / title / markdown message / severity).

Frontends render an ``Insight`` however they like (Streamlit ``render_insight_card``, a Dash
card). Messages are markdown; currency uses ``format_currency_md`` so ``$`` is pre-escaped.
"""

from dataclasses import dataclass

import pandas as pd

from src.expenses.analytics import (
    get_financial_health_score,
    get_month_pace_projection,
    get_next_month_commitment_metrics,
    get_spending_anomalies,
)
from src.expenses.config import (
    ANOMALY_MIN_CATEGORY_TX,
    ANOMALY_Z_THRESHOLD,
    INSTALLMENT_BURDEN_WARNING_PCT,
    REFERENCE_BUDGET_LIMIT,
    format_currency_br,
    format_currency_md,
)


@dataclass(frozen=True)
class Insight:
    icon: str
    title: str
    message: str
    severity: str = "info"


HEALTH_RATING_META = {
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
MOMENTUM_META = {
    "rising": {"icon": "📈", "severity": "warning", "verb": "trending up"},
    "falling": {"icon": "📉", "severity": "good", "verb": "trending down"},
    "stable": {"icon": "➡️", "severity": "info", "verb": "stable"},
}


def health_insight(df_full: pd.DataFrame) -> Insight | None:
    health = get_financial_health_score(df_full)
    if not health["has_data"]:
        return None
    meta = HEALTH_RATING_META[health["rating"]]
    factor = health["top_factor"]
    factor_label = _HEALTH_FACTOR_LABELS.get(factor, factor)
    factor_score = health["components"].get(factor, 0)
    return Insight(
        meta["icon"],
        f"Financial Health Score: {health['score']}/100 ({health['rating']})",
        "Composite score across installment burden, anomalies, upcoming budget proximity, and "
        f"spending volatility. Weakest factor: **{factor_label}** ({factor_score:.0f}/100).",
        meta["severity"],
    )


def next_month_insight(
    df_full: pd.DataFrame, reference_limit: float = REFERENCE_BUDGET_LIMIT
) -> Insight | None:
    m = get_next_month_commitment_metrics(df_full, reference_limit=reference_limit)
    if not m["has_data"]:
        return None
    cost = format_currency_md(m["next_month_cost"])
    diff = format_currency_md(abs(m["diff_from_limit"]))
    limit = format_currency_md(reference_limit)
    body = (
        f"**{cost}** ({m['pct_of_limit']:.1f}% of the {limit} reference limit) is already "
        f"committed across **{m['num_installments']}** active installment(s) — "
    )
    if m["is_over_limit"]:
        return Insight(
            "⚠️",
            f"Upcoming Month Budget Warning ({m['next_month']})",
            body + f"**+{diff} above** the reference limit.",
            "critical",
        )
    return Insight(
        "🔒",
        f"Upcoming Month Budget On Track ({m['next_month']})",
        body + f"**{diff} remaining** within budget.",
        "good",
    )


def _mom_insight(kpis: dict) -> Insight:
    delta = kpis["mom_delta_pct"]
    if delta > 0:
        return Insight(
            "📈",
            "Spending Increased",
            f"Your latest invoice is **{delta:.1f}%** higher than the previous one.",
            "warning",
        )
    if delta < 0:
        return Insight(
            "📉",
            "Spending Decreased",
            f"Great job! Your latest invoice dropped by **{abs(delta):.1f}%**.",
            "good",
        )
    return Insight(
        "⚖️",
        "Spending Stable",
        "Your latest invoice is exactly the same as the previous one.",
        "info",
    )


def _installment_insight(kpis: dict) -> Insight:
    pct = kpis["installment_pct"]
    if pct > INSTALLMENT_BURDEN_WARNING_PCT:
        return Insight(
            "💳",
            "High Installment Burden",
            f"**{pct:.1f}%** of your spending is tied up in installments.",
            "warning",
        )
    return Insight(
        "💳",
        "Healthy Installment Ratio",
        f"Only **{pct:.1f}%** of your spending is tied up in installments.",
        "good",
    )


def _anomaly_summary_insight(df_expenses: pd.DataFrame) -> Insight:
    anomalies = get_spending_anomalies(
        df_expenses, z_threshold=ANOMALY_Z_THRESHOLD, min_category_tx=ANOMALY_MIN_CATEGORY_TX
    )
    if anomalies.empty:
        return Insight(
            "✅",
            "No Anomalies Detected",
            "All transactions fall within the expected spending pattern for their category.",
            "good",
        )
    return Insight(
        "⚠️",
        f"{len(anomalies)} Unusual Transaction(s)",
        "Some purchases are well above their category's typical pattern. See the "
        "**📈 Trends & Insights** tab for details.",
        "warning",
    )


def _pace_insight(df_full: pd.DataFrame) -> Insight:
    pace = get_month_pace_projection(df_full)
    if not pace["has_data"]:
        return Insight(
            "📆", "Spending Pace", "Not enough data yet to project this month's pace.", "info"
        )
    projected = format_currency_md(pace["projected_total"])
    if pace["status"] in ("hot", "cold"):
        hot = pace["status"] == "hot"
        return Insight(
            "🔥" if hot else "🧊",
            "Spending Pace Running Hot" if hot else "Spending Pace Running Cold",
            f"**{pace['current_month']}** is projected to reach **{projected}** "
            f"({pace['pace_delta_pct']:+.1f}% vs your recent average).",
            "warning" if hot else "good",
        )
    return Insight(
        "📆",
        "Spending Pace Normal",
        f"**{pace['current_month']}** is tracking close to your recent monthly average "
        f"(projected **{projected}**).",
        "info",
    )


def automated_insights(
    kpis: dict, df_expenses: pd.DataFrame, df_full: pd.DataFrame
) -> list[Insight]:
    """The five 'Automated Insights' cards of the General Dashboard, in display order."""
    return [
        Insight(
            "🎯",
            "Top Expense Driver",
            f"**{kpis['top_cat_name']}** consumes **{kpis['top_cat_pct']:.1f}%** of your total net "
            "spending.",
            "info",
        ),
        _mom_insight(kpis),
        _installment_insight(kpis),
        _anomaly_summary_insight(df_expenses),
        _pace_insight(df_full),
    ]


def category_momentum_insight(momentum_row, category_label: str) -> Insight:
    """Callout for one category's 3-month momentum row (from ``get_category_momentum``)."""
    meta = MOMENTUM_META[momentum_row["direction"]]
    return Insight(
        meta["icon"],
        f"{category_label} is {meta['verb']}",
        f"Changed **{momentum_row['pct_change_over_window']:+.1f}%** over the last 3 months (now "
        f"**{format_currency_br(momentum_row['last_month_value'])}**/month).",
        meta["severity"],
    )


def top_momentum_insight(momentum: pd.DataFrame) -> Insight:
    """Headline card for the Trends tab: the top rising category, or an all-clear."""
    rising = momentum[momentum["direction"] == "rising"]
    if rising.empty:
        return Insight(
            "🧭",
            "Category Momentum",
            "No category is on a consistent 3-month rising trend right now.",
            "good",
        )
    top = rising.iloc[0]
    return Insight(
        "📈",
        f"Rising: {top['category_label']}",
        f"Up **{top['pct_change_over_window']:+.1f}%** over the last 3 months "
        f"(now **{format_currency_br(top['last_month_value'])}**/month).",
        "warning",
    )


def frequency_change_insight(freq_change: pd.DataFrame) -> Insight:
    top = freq_change.iloc[0]
    increased = top["direction"] == "increased"
    word = "buying more often from" if increased else "buying less often from"
    return Insight(
        "🔀" if increased else "📉",
        f"Most Notable Change: {top['id']}",
        f"You're {word} **{top['id']}** — **{top['recent_monthly_rate']:.1f}x/month** recently vs. "
        f"**{top['baseline_monthly_rate']:.1f}x/month** historically ({top['change_pct']:+.0f}%).",
        "warning" if increased else "info",
    )


def anomalies_insight(anomalies: pd.DataFrame) -> Insight:
    if anomalies.empty:
        return Insight(
            "✅",
            "No Anomalies Detected",
            "All transactions in the selected period fall within the expected spending pattern "
            "for their category.",
            "good",
        )
    return Insight(
        "⚠️",
        f"{len(anomalies)} Unusual Transaction(s)",
        "Detected in the selected period — well above their category's typical pattern.",
        "warning",
    )


def executive_summary_insight(df_exp: pd.DataFrame) -> Insight:
    """Executive Spending Summary for the Reports tab (``df_exp`` already excludes payments)."""
    total = df_exp["cost"].sum()
    monthly = df_exp.groupby("year_month")["cost"].sum()
    peak_month = monthly.idxmax() if not df_exp.empty else "N/A"
    peak_value = monthly.max() if not df_exp.empty else 0

    ranking = df_exp.groupby("category_label")["cost"].sum().sort_values(ascending=False)
    top1 = ranking.index[0] if len(ranking) > 0 else "N/A"
    top1_val = ranking.iloc[0] if len(ranking) > 0 else 0
    top2 = ranking.index[1] if len(ranking) > 1 else "N/A"
    top2_val = ranking.iloc[1] if len(ranking) > 1 else 0

    nf = df_exp[df_exp["category"] == "not_found"]
    nf_val = nf["cost"].sum()
    nf_pct = (nf_val / total * 100) if total > 0 else 0.0
    severity = "warning" if nf_pct > 15 else "info" if nf_pct > 0 else "good"

    def pct(v):
        return v / total * 100 if total else 0

    return Insight(
        "📌",
        "Executive Spending Summary",
        f"In the analyzed period, total accumulated expenses were **{format_currency_br(total)}**. "
        f"The peak spending month was **{peak_month}** with a total of "
        f"**{format_currency_br(peak_value)}**. Top spending categories were **{top1}** "
        f"({format_currency_br(top1_val)}, {pct(top1_val):.1f}%) and **{top2}** "
        f"({format_currency_br(top2_val)}, {pct(top2_val):.1f}%). There are **{len(nf)}** "
        f"transaction(s) without categorization totaling **{format_currency_br(nf_val)}** "
        f"({nf_pct:.1f}% of total).",
        severity,
    )
