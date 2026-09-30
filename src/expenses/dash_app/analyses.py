"""View models for the secondary tabs (Tendências, Atenção, Categorias, Relatórios).

Each builder takes the same controls as `data.build_view`, slices with `data.slice_data` and only
calls `analytics.py`. Results are plain dicts of numbers and DataFrames; `layout.py` renders them.
"""

import pandas as pd

from src.expenses.analytics import (
    _exclude_payments,
    get_category_momentum,
    get_future_installments_details,
    get_future_installments_projection,
    get_merchant_frequency_change,
    get_next_month_commitment_metrics,
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
    REFERENCE_BUDGET_LIMIT,
)
from src.expenses.dash_app.data import _MONTHS_PT, slice_data
from src.expenses.dash_app.fmt import CATEGORY_LABELS_PT, WEEKDAYS_PT

TREND_LABELS = {"up": "Em alta", "down": "Em queda", "stable": "Estável"}
MOMENTUM_LABELS = {"rising": "▲ Subindo", "falling": "▼ Caindo", "stable": "Estável"}
STATUS_LABELS = {"Increased": "▲ Aumentou", "Decreased": "▼ Diminuiu", "Stable": "Estável"}
FREQUENCY_LABELS = {"increased": "▲ Mais frequente", "decreased": "▼ Menos frequente"}


def trends_view(df_full: pd.DataFrame, period=None, holders=None, categories=None) -> dict:
    """Is spending changing? Linear trend, previous period, same months last year, momentum."""
    sliced = slice_data(df_full, period, holders, categories)
    df_scope = sliced.df_scope
    trend = get_spending_trend(_exclude_payments(sliced.df) if not sliced.df.empty else sliced.df)
    yoy = get_year_over_year_comparison(df_scope)
    if not yoy.empty:
        yoy = yoy.assign(month_name=[_MONTHS_PT[int(m) - 1] for m in yoy["month_num"]])
    return {
        "is_empty": sliced.df.empty,
        "heatmap": category_month_matrix(sliced.df, sliced.months),
        "trend": trend,
        "direction": TREND_LABELS[trend["direction"]],
        "pop": get_period_over_period_comparison(df_scope, sliced.months),
        "yoy": yoy,
        "momentum": get_category_momentum(df_scope, window=3),
    }


def watchlist_view(df_full: pd.DataFrame, period=None, holders=None, categories=None) -> dict:
    """What deserves a second look? Recurring charges, outliers, uncategorized, frequency shifts."""
    sliced = slice_data(df_full, period, holders, categories)
    df, df_scope = sliced.df, sliced.df_scope
    empty = {
        "is_empty": True,
        "recurring": pd.DataFrame(),
        "anomalies": pd.DataFrame(),
        "uncategorized": pd.DataFrame(),
        "frequency": pd.DataFrame(),
        "new_merchants": pd.DataFrame(),
        "fixed_cost": 0.0,
        "uncategorized_total": 0.0,
        "uncategorized_pct": 0.0,
    }
    if df.empty:
        return empty

    recurring = get_recurring_merchants(
        df_scope, min_months=RECURRING_MIN_MONTHS, max_cv=RECURRING_MAX_CV
    )
    anomalies = get_spending_anomalies(
        df, z_threshold=ANOMALY_Z_THRESHOLD, min_category_tx=ANOMALY_MIN_CATEGORY_TX
    )
    positive = _exclude_payments(df)
    positive = positive[positive["cost"] > 0]
    not_found = positive[positive["category"] == "not_found"]
    uncategorized = (
        not_found.groupby("id")
        .agg(tx=("cost", "count"), total=("cost", "sum"), last=("date_buy", "max"))
        .reset_index()
        .sort_values("total", ascending=False)
        .reset_index(drop=True)
    )
    total = float(positive["cost"].sum())
    nf_total = float(not_found["cost"].sum())
    return {
        **empty,
        "is_empty": False,
        "recurring": recurring,
        "anomalies": anomalies,
        "uncategorized": uncategorized,
        "frequency": get_merchant_frequency_change(df_scope),
        "new_merchants": new_merchants(df, df_scope, sliced.months),
        "fixed_cost": float(recurring["avg_monthly_cost"].sum()) if not recurring.empty else 0.0,
        "uncategorized_total": nf_total,
        "uncategorized_pct": nf_total / total * 100 if total > 0 else 0.0,
    }


def category_options(df_full: pd.DataFrame, period=None, holders=None, categories=None) -> list:
    """(key, label) of categories with spending in the selection, largest first."""
    df = slice_data(df_full, period, holders, categories).df
    if df.empty:
        return []
    positive = _exclude_payments(df)
    totals = positive[positive["cost"] > 0].groupby("category")["cost"].sum()
    return [(c, CATEGORY_LABELS_PT.get(c, c)) for c in totals.sort_values(ascending=False).index]


def category_view(
    df_full: pd.DataFrame, period=None, holders=None, categories=None, selected=None
) -> dict:
    """What is inside one category? Size, share, momentum, history, merchants, largest purchases."""
    options = category_options(df_full, period, holders, categories)
    keys = [key for key, _ in options]
    if not keys:
        return {"is_empty": True, "options": [], "selected": None}
    selected = selected if selected in keys else keys[0]

    sliced = slice_data(df_full, period, holders, categories)
    positive = _exclude_payments(sliced.df)
    positive = positive[positive["cost"] > 0]
    cat = positive[positive["category"] == selected]
    total = float(cat["cost"].sum())
    count = len(cat)
    momentum = get_category_momentum(sliced.df, window=3)
    row = momentum[momentum["category"] == selected]

    history = (
        cat.groupby("year_month", as_index=False)["cost"]
        .sum()
        .set_index("year_month")
        .reindex(sliced.months, fill_value=0.0)
        .reset_index()
    )
    merchants = (
        cat.groupby("id", as_index=False)["cost"]
        .sum()
        .sort_values("cost", ascending=False)
        .head(8)
        .reset_index(drop=True)
    )
    return {
        "is_empty": False,
        "options": options,
        "selected": selected,
        "label": CATEGORY_LABELS_PT.get(selected, selected),
        "total": total,
        "share_pct": total / float(positive["cost"].sum()) * 100 if total else 0.0,
        "count": count,
        "avg_ticket": total / count if count else 0.0,
        "momentum_pct": float(row["pct_change_over_window"].iloc[0]) if not row.empty else None,
        "history": history,
        "merchants": merchants,
        "largest": cat.nlargest(10, "cost")[
            ["date_buy", "id", "cost", "installment", "total_installments"]
        ].reset_index(drop=True),
    }


def reports_view(df_full: pd.DataFrame, period=None, holders=None, categories=None) -> dict:
    """What is already committed ahead, and the invoice totals behind the selection."""
    sliced = slice_data(df_full, period, holders, categories)
    df, df_scope = sliced.df, sliced.df_scope
    metrics = get_next_month_commitment_metrics(df_scope, REFERENCE_BUDGET_LIMIT)
    if df_scope.empty:
        projection = details = pd.DataFrame()
    else:
        projection = (
            get_future_installments_projection(df_scope)
            .groupby("future_month", as_index=False)["cost"]
            .sum()
            .sort_values("future_month")
        )
        details = get_future_installments_details(df_scope)
        if not details.empty:
            details = details.sort_values(["future_month", "cost"], ascending=[True, False])

    invoices = pd.DataFrame()
    if not df.empty:
        invoices = (
            df.groupby("year_month")
            .agg(
                tx=("cost", "count"),
                gross=("cost", lambda s: s[s > 0].sum()),
                refunds=("cost", lambda s: s[s < 0].sum()),
                net=("cost", "sum"),
            )
            .reset_index()
            .sort_values("year_month", ascending=False)
            .reset_index(drop=True)
        )
    return {
        "is_empty": df.empty,
        "metrics": metrics,
        "limit": REFERENCE_BUDGET_LIMIT,
        "projection": projection,
        "details": details.reset_index(drop=True) if not details.empty else details,
        "invoices": invoices,
        "rows": len(df),
    }


def export_frame(df_full: pd.DataFrame, period=None, holders=None, categories=None) -> pd.DataFrame:
    """The selected rows as a tidy table for the CSV download."""
    df = slice_data(df_full, period, holders, categories).df
    if df.empty:
        return pd.DataFrame()
    return pd.DataFrame(
        {
            "fatura": df["year_month"],
            "data_fatura": pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d"),
            "data_compra": pd.to_datetime(df["date_buy"]).dt.strftime("%Y-%m-%d"),
            "estabelecimento": df["id"],
            "titular": df["source_debt"],
            "categoria": df["category_label"],
            "valor": df["cost"].round(2),
            "parcela": df["installment"],
            "total_parcelas": df["total_installments"],
        }
    ).sort_values(["data_compra", "estabelecimento"], ascending=[False, True])


# --------------------------------------------------------------------------- new analyses

TICKET_BANDS = [0, 50, 100, 250, 500, 1000, float("inf")]
TICKET_LABELS = ["até 50", "50–100", "100–250", "250–500", "500–1 mil", "1 mil+"]
_ENGLISH_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _purchases(df: pd.DataFrame) -> pd.DataFrame:
    """Positive, non-payment rows: actual purchases (refunds excluded)."""
    if df.empty:
        return df
    eff = _exclude_payments(df)
    return eff[eff["cost"] > 0]


def category_month_matrix(df: pd.DataFrame, months: list[str], top_n: int = 12) -> pd.DataFrame:
    """Purchases per category (rows, largest first) × invoice month (columns, chronological)."""
    purchases = _purchases(df)
    if purchases.empty:
        return pd.DataFrame()
    matrix = purchases.pivot_table(
        index="category", columns="year_month", values="cost", aggfunc="sum", fill_value=0.0
    ).reindex(columns=months, fill_value=0.0)
    matrix = matrix.loc[matrix.sum(axis=1).sort_values(ascending=False).index].head(top_n)
    matrix.index = [CATEGORY_LABELS_PT.get(c, c) for c in matrix.index]
    return matrix


def new_merchants(df: pd.DataFrame, df_scope: pd.DataFrame, months: list[str]) -> pd.DataFrame:
    """Merchants whose first purchase in the whole history falls inside the selected period.
    Empty when the period starts at the first month on record (everything would be "new")."""
    purchases, history = _purchases(df), _purchases(df_scope)
    if purchases.empty or not months or history["year_month"].min() >= months[0]:
        return pd.DataFrame()
    first_seen = history.groupby("id")["year_month"].min()
    new_ids = first_seen[first_seen >= months[0]].index
    rows = purchases[purchases["id"].isin(new_ids)]
    if rows.empty:
        return pd.DataFrame()
    return (
        rows.groupby("id")
        .agg(
            category=("category", "first"),
            category_label=("category_label", "first"),
            first=("date_buy", "min"),
            tx=("cost", "count"),
            total=("cost", "sum"),
        )
        .reset_index()
        .sort_values("total", ascending=False)
        .reset_index(drop=True)
    )


def habits_view(df_full: pd.DataFrame, period=None, holders=None, categories=None) -> dict:
    """How do I spend? Installments vs single payment, ticket sizes, weekdays, cardholders and
    merchant concentration — all over purchases (refunds and invoice payments excluded)."""
    sliced = slice_data(df_full, period, holders, categories)
    purchases = _purchases(sliced.df)
    if purchases.empty:
        return {"is_empty": True}

    total = float(purchases["cost"].sum())
    count = len(purchases)
    months = max(1, len(sliced.months))

    split = (
        purchases.assign(
            kind=purchases["is_installment"].map({True: "Parcelado", False: "À vista"})
        )
        .pivot_table(
            index="year_month", columns="kind", values="cost", aggfunc="sum", fill_value=0.0
        )
        .reindex(index=sliced.months, columns=["À vista", "Parcelado"], fill_value=0.0)
    )
    installment_total = float(split["Parcelado"].sum())

    bands = (
        purchases.assign(
            band=pd.cut(purchases["cost"], TICKET_BANDS, labels=TICKET_LABELS, right=False)
        )
        .groupby("band", observed=False)["cost"]
        .agg(["count", "sum"])
        .reindex(TICKET_LABELS, fill_value=0)
        .reset_index()
        .rename(columns={"count": "tx", "sum": "total"})
    )
    bands["share"] = bands["total"] / total * 100

    weekday = (
        purchases.assign(day=purchases["date_buy"].dt.day_name())
        .groupby("day")["cost"]
        .agg(["count", "sum"])
        .reindex(_ENGLISH_WEEKDAYS, fill_value=0)
        .reset_index()
        .rename(columns={"count": "tx", "sum": "total"})
    )
    weekday["day"] = WEEKDAYS_PT
    weekday["avg_ticket"] = (weekday["total"] / weekday["tx"].where(weekday["tx"] > 0)).fillna(0.0)

    holders_monthly = (
        purchases.assign(holder=purchases["source_debt"].replace("", "Sem titular"))
        .pivot_table(
            index="year_month", columns="holder", values="cost", aggfunc="sum", fill_value=0.0
        )
        .reindex(index=sliced.months, fill_value=0.0)
    )

    by_merchant = purchases.groupby("id")["cost"].sum().sort_values(ascending=False)
    top10_share = float(by_merchant.head(10).sum()) / total * 100
    # How many merchants make up 80% of spending (Pareto).
    cumulative = by_merchant.cumsum() / total
    pareto_n = int((cumulative < 0.8).sum()) + 1

    return {
        "is_empty": False,
        "total": total,
        "count": count,
        "per_month": count / months,
        "avg_ticket": total / count,
        "median_ticket": float(purchases["cost"].median()),
        "installment_share": installment_total / total * 100,
        "merchants": int(by_merchant.size),
        "top10_share": top10_share,
        "pareto_n": min(pareto_n, int(by_merchant.size)),
        "split": split,
        "bands": bands,
        "weekday": weekday,
        "holders": holders_monthly,
    }
