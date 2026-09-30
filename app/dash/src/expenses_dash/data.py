"""View model for the Dash dashboard.

`build_view` turns the full Silver frame plus the three controls (period, card holders,
categories) into a `DashboardView`. Every number comes from `analytics.py` / `filters.py`.
"""

from dataclasses import dataclass, field

import pandas as pd

from expenses.analytics import (
    _exclude_payments,
    calculate_kpis,
    get_future_installments_projection,
    get_monthly_grouped,
    get_moving_average,
    get_next_month_commitment_metrics,
    get_top_merchants,
)
from expenses.config import REFERENCE_BUDGET_LIMIT
from expenses.filters import DEFAULT_FILTERS, apply_filters, resolve_default_months
from expenses_dash.fmt import CATEGORY_LABELS_PT, brl, integer, pct

# Period choices (keys are `filters.PERIOD_OPTIONS` values understood by resolve_default_months).
PERIOD_LABELS = {
    "Last 3 months": "Últimos 3 meses",
    "Last 6 months": "Últimos 6 meses",
    "Last 12 months": "Últimos 12 meses",
    "All History": "Todo o histórico",
}
DEFAULT_PERIOD = "Last 6 months"
TOP_N = 10
_MONTHS_PT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def _frame(*columns: str):
    return field(default_factory=lambda: pd.DataFrame(columns=list(columns)))


@dataclass
class DashboardView:
    is_empty: bool = True
    period_label: str = ""
    months: list[str] = field(default_factory=list)
    last_invoice: str = ""
    total: float = 0.0
    avg_monthly: float = 0.0
    tx_count: int = 0
    last_month: str = ""
    last_month_value: float = 0.0
    last_month_delta_pct: float | None = None
    next_month: str = ""
    next_month_cost: float = 0.0
    budget_limit: float = REFERENCE_BUDGET_LIMIT
    pct_of_limit: float = 0.0
    monthly: pd.DataFrame = _frame("year_month", "cost", "moving_avg")
    by_category: pd.DataFrame = _frame("category", "category_label", "cost")
    top_merchants: pd.DataFrame = _frame("id", "total_spent", "tx_count", "category")
    commitments: pd.DataFrame = _frame("future_month", "cost")
    largest: pd.DataFrame = _frame("date_buy", "id", "category", "category_label", "cost")


def month_label(year_month: str) -> str:
    """'2026-03' -> 'mar/26'."""
    try:
        year, month = str(year_month).split("-")
        return f"{_MONTHS_PT[int(month) - 1]}/{year[2:]}"
    except (ValueError, IndexError):
        return str(year_month)


@dataclass
class Slice:
    """The frames every tab starts from.

    ``df`` — the selected period, holders and categories (payments removed).
    ``df_scope`` — the same holders/categories over the full history: installment projections,
    recurring charges and comparisons need months outside the selected period.
    """

    df: pd.DataFrame
    df_scope: pd.DataFrame
    months: list[str]
    period_label: str
    last_invoice: str


def slice_data(
    df_full: pd.DataFrame,
    period: str | None = DEFAULT_PERIOD,
    holders: list[str] | None = None,
    categories: list[str] | None = None,
) -> Slice:
    period = period if period in PERIOD_LABELS else DEFAULT_PERIOD
    if df_full.empty:
        return Slice(pd.DataFrame(), pd.DataFrame(), [], PERIOD_LABELS[period], "")
    all_months = sorted(df_full["year_month"].dropna().unique(), reverse=True)
    months = resolve_default_months(period, all_months)
    scope = {
        **DEFAULT_FILTERS,
        "selected_holders": list(holders or []),
        "selected_categories": list(categories or []),
    }
    return Slice(
        df=_pt_labels(apply_filters(df_full, {**scope, "selected_months": months})),
        df_scope=_pt_labels(apply_filters(df_full, scope)),
        months=sorted(months),
        period_label=PERIOD_LABELS[period],
        last_invoice=pd.Timestamp(df_full["date"].max()).strftime("%d/%m/%Y"),
    )


def _pt_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Portuguese category names in ``category_label`` (every table and chart reads it)."""
    if df.empty:
        return df
    return df.assign(category_label=df["category"].map(CATEGORY_LABELS_PT))


def filter_options(df_full: pd.DataFrame) -> dict:
    """Choices for the controls: periods, card holders and (key, label) categories."""
    periods = list(PERIOD_LABELS.items())
    if df_full.empty:
        return {"periods": periods, "holders": [], "categories": []}
    holders = sorted(h for h in df_full["source_debt"].dropna().unique() if str(h).strip())
    categories = sorted(
        ((c, CATEGORY_LABELS_PT.get(c, c)) for c in df_full["category"].dropna().unique()),
        key=lambda kv: kv[1],
    )
    return {"periods": periods, "holders": holders, "categories": categories}


def build_view(
    df_full: pd.DataFrame,
    period: str = DEFAULT_PERIOD,
    holders: list[str] | None = None,
    categories: list[str] | None = None,
) -> DashboardView:
    """Everything the dashboard shows for one selection of the controls."""
    sliced = slice_data(df_full, period, holders, categories)
    view = DashboardView(period_label=sliced.period_label)
    if df_full.empty:
        return view

    df, df_scope = sliced.df, sliced.df_scope
    view.months = sliced.months
    view.last_invoice = sliced.last_invoice
    _fill_commitments(view, df_scope)
    if df.empty:
        return view

    kpis = calculate_kpis(df, df_scope)
    view.is_empty = False
    view.total = kpis["total_spent"]
    view.avg_monthly = kpis["avg_monthly_spent"]
    view.tx_count = kpis["total_tx"]

    view.monthly = get_moving_average(df, window=3)
    view.last_month = str(view.monthly["year_month"].iloc[-1])
    view.last_month_value = float(view.monthly["cost"].iloc[-1])
    if len(view.monthly) >= 2 and view.monthly["cost"].iloc[-2] > 0:
        previous = float(view.monthly["cost"].iloc[-2])
        view.last_month_delta_pct = (view.last_month_value - previous) / previous * 100

    view.by_category = (
        get_monthly_grouped(df)
        .groupby(["category", "category_label"], as_index=False)["cost"]
        .sum()
        .sort_values("cost", ascending=False)
        .reset_index(drop=True)
    )
    view.top_merchants = (
        get_top_merchants(df, top_n=TOP_N)
        .sort_values("total_spent", ascending=False)
        .reset_index(drop=True)
    )
    view.largest = (
        _exclude_payments(df)
        .nlargest(TOP_N, "cost")[["date_buy", "id", "category", "category_label", "cost"]]
        .reset_index(drop=True)
    )
    return view


def _fill_commitments(view: DashboardView, df_scope: pd.DataFrame) -> None:
    if df_scope.empty:
        return
    metrics = get_next_month_commitment_metrics(df_scope, REFERENCE_BUDGET_LIMIT)
    view.next_month = metrics["next_month"] if metrics["has_data"] else ""
    view.next_month_cost = metrics["next_month_cost"]
    view.pct_of_limit = metrics["pct_of_limit"]
    projection = get_future_installments_projection(df_scope)
    view.commitments = (
        projection.groupby("future_month", as_index=False)["cost"]
        .sum()
        .sort_values("future_month")
        .reset_index(drop=True)
    )


def kpi_cards(view: DashboardView) -> list[dict]:
    """The four headline numbers as display-ready dicts: label, value, note, help, tone.

    ``tone`` colours the note: ``bad`` (spending up / over the limit), ``good``, or ``neutral``.
    """
    delta, delta_tone = spend_delta(view.last_month_delta_pct, "vs mês anterior")
    next_label = month_label(view.next_month) if view.next_month else "—"
    return [
        {
            "label": "Gasto no período",
            "value": brl(view.total),
            "note": f"{integer(view.tx_count)} compras · {len(view.months)} meses",
            "help": "Compras menos estornos; pagamentos de fatura não entram.",
        },
        {
            "label": "Média mensal",
            "value": brl(view.avg_monthly),
            "note": view.period_label,
            "help": "Gasto líquido do período dividido pelo número de faturas.",
        },
        {
            "label": f"Fatura {month_label(view.last_month)}"
            if view.last_month
            else "Última fatura",
            "value": brl(view.last_month_value),
            "note": delta,
            "tone": delta_tone,
            "help": "Último mês do período comparado ao mês imediatamente anterior.",
        },
        {
            "label": f"Parcelas {next_label}",
            "value": brl(view.next_month_cost),
            "note": f"{pct(view.pct_of_limit, 0)} do limite de {brl(view.budget_limit, 0)}",
            "tone": "bad" if view.pct_of_limit > 100 else "neutral",
            "help": "Parcelas já contratadas na próxima fatura, contra REFERENCE_BUDGET_LIMIT.",
        },
    ]


def spend_delta(change_pct: float | None, suffix: str) -> tuple[str, str]:
    """('▲ 8,6% vs …', tone) for a spending change: rising spend is ``bad``, falling is ``good``."""
    if change_pct is None:
        return "sem base de comparação", "neutral"
    arrow = "▲" if change_pct >= 0 else "▼"
    tone = "neutral" if abs(change_pct) < 0.5 else ("bad" if change_pct > 0 else "good")
    return f"{arrow} {pct(abs(change_pct))} {suffix}", tone
