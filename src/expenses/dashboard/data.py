"""Framework-agnostic view model for the dashboard.

`build_view` turns the full Silver frame plus the three dashboard controls (period, card holders,
categories) into a `DashboardView` that both the Streamlit and the Dash frontends render as-is.
Every number comes from `analytics.py` / `filters.py`; nothing here talks to a UI framework.
"""

from dataclasses import dataclass, field

import pandas as pd

from src.expenses.analytics import (
    _exclude_payments,
    calculate_kpis,
    get_future_installments_projection,
    get_monthly_grouped,
    get_moving_average,
    get_next_month_commitment_metrics,
    get_top_merchants,
)
from src.expenses.config import CATEGORY_LABELS, REFERENCE_BUDGET_LIMIT, format_currency_br
from src.expenses.filters import DEFAULT_FILTERS, apply_filters, resolve_default_months

# Period choices offered by the dashboard (values are the `filters.PERIOD_OPTIONS` keys).
PERIOD_LABELS = {
    "Last 3 months": "Últimos 3 meses",
    "Last 6 months": "Últimos 6 meses",
    "Last 12 months": "Últimos 12 meses",
    "All History": "Todo o histórico",
}
DEFAULT_PERIOD = "Last 6 months"
TOP_N = 10


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
    monthly: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=["year_month", "cost", "moving_avg"])
    )
    by_category: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=["category_label", "cost"])
    )
    top_merchants: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=["id", "total_spent", "tx_count"])
    )
    commitments: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=["future_month", "cost"])
    )
    largest: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=["date_buy", "id", "category_label", "cost"])
    )


def filter_options(df_full: pd.DataFrame) -> dict:
    """Choices for the dashboard controls: periods, card holders and (key, label) categories."""
    periods = list(PERIOD_LABELS.items())
    if df_full.empty:
        return {"periods": periods, "holders": [], "categories": []}
    holders = sorted(h for h in df_full["source_debt"].dropna().unique() if str(h).strip())
    categories = sorted(
        ((c, CATEGORY_LABELS.get(c, c)) for c in df_full["category"].dropna().unique()),
        key=lambda kv: kv[1],
    )
    return {"periods": periods, "holders": holders, "categories": categories}


def build_view(
    df_full: pd.DataFrame,
    period: str = DEFAULT_PERIOD,
    holders: list[str] | None = None,
    categories: list[str] | None = None,
) -> DashboardView:
    """Computes everything the dashboard shows for one selection of the controls."""
    period = period if period in PERIOD_LABELS else DEFAULT_PERIOD
    view = DashboardView(period_label=PERIOD_LABELS[period])
    if df_full.empty:
        return view

    all_months = sorted(df_full["year_month"].dropna().unique(), reverse=True)
    months = resolve_default_months(period, all_months)
    scope_filters = {
        **DEFAULT_FILTERS,
        "selected_holders": list(holders or []),
        "selected_categories": list(categories or []),
    }
    # Holder/category scope without the period: future commitments live past the selected months.
    df_scope = apply_filters(df_full, scope_filters)
    df = apply_filters(df_full, {**scope_filters, "selected_months": months})

    view.months = sorted(months)
    view.last_invoice = pd.Timestamp(df_full["date"].max()).strftime("%d/%m/%Y")
    view.commitments, commitment = _commitments(df_scope)
    view.next_month = commitment["next_month"] if commitment["has_data"] else ""
    view.next_month_cost = commitment["next_month_cost"]
    view.pct_of_limit = commitment["pct_of_limit"]
    if df.empty:
        return view

    kpis = calculate_kpis(df, df_scope)
    view.is_empty = False
    view.total = kpis["total_spent"]
    view.avg_monthly = kpis["avg_monthly_spent"]
    view.tx_count = kpis["total_tx"]

    monthly = get_moving_average(df, window=3)
    view.monthly = monthly
    view.last_month = str(monthly["year_month"].iloc[-1])
    view.last_month_value = float(monthly["cost"].iloc[-1])
    if len(monthly) >= 2 and monthly["cost"].iloc[-2] > 0:
        prev = float(monthly["cost"].iloc[-2])
        view.last_month_delta_pct = (view.last_month_value - prev) / prev * 100

    view.by_category = (
        get_monthly_grouped(df)
        .groupby("category_label", as_index=False)["cost"]
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
        .nlargest(TOP_N, "cost")[["date_buy", "id", "category_label", "cost"]]
        .reset_index(drop=True)
    )
    return view


def _commitments(df_scope: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    metrics = get_next_month_commitment_metrics(df_scope, REFERENCE_BUDGET_LIMIT)
    if df_scope.empty:
        return pd.DataFrame(columns=["future_month", "cost"]), metrics
    projection = get_future_installments_projection(df_scope)
    by_month = (
        projection.groupby("future_month", as_index=False)["cost"].sum().sort_values("future_month")
    )
    return by_month.reset_index(drop=True), metrics


def month_label(year_month: str) -> str:
    """'2026-03' -> 'mar/26'."""
    names = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    try:
        year, month = year_month.split("-")
        return f"{names[int(month) - 1]}/{year[2:]}"
    except (ValueError, IndexError, AttributeError):
        return str(year_month)


def kpi_cards(view: DashboardView) -> list[dict]:
    """The four headline numbers as display-ready dicts: label, value, note, help."""
    if view.last_month_delta_pct is None:
        delta = "sem mês anterior"
    else:
        arrow = "▲" if view.last_month_delta_pct >= 0 else "▼"
        delta = f"{arrow} {abs(view.last_month_delta_pct):.1f}% vs mês anterior"
    next_label = month_label(view.next_month) if view.next_month else "—"
    return [
        {
            "label": "Gasto no período",
            "value": format_currency_br(view.total),
            "note": f"{view.tx_count:,} compras · {len(view.months)} meses".replace(",", "."),
            "help": "Compras menos estornos; pagamentos de fatura não entram.",
        },
        {
            "label": "Média mensal",
            "value": format_currency_br(view.avg_monthly),
            "note": view.period_label,
            "help": "Gasto líquido do período dividido pelo número de faturas.",
        },
        {
            "label": f"Fatura {month_label(view.last_month)}"
            if view.last_month
            else "Última fatura",
            "value": format_currency_br(view.last_month_value),
            "note": delta,
            "help": "Último mês do período comparado ao mês imediatamente anterior.",
        },
        {
            "label": f"Parcelas {next_label}",
            "value": format_currency_br(view.next_month_cost),
            "note": f"{view.pct_of_limit:.0f}% do limite de {format_currency_br(view.budget_limit)}",
            "help": "Parcelas já contratadas que caem na próxima fatura (REFERENCE_BUDGET_LIMIT).",
        },
    ]
