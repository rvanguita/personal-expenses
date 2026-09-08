import calendar

import numpy as np
import pandas as pd

from src.expenses.config import (
    ANOMALY_MIN_CATEGORY_TX,
    ANOMALY_Z_THRESHOLD,
    RECURRING_MAX_CV,
    RECURRING_MIN_MONTHS,
    REFERENCE_BUDGET_LIMIT,
)


def _exclude_payments(df: pd.DataFrame) -> pd.DataFrame:
    """Returns a copy of df excluding payment settlement rows (e.g. Pagamentos Validos Normais)."""
    if "is_payment" in df.columns:
        return df[~df["is_payment"]].copy()
    return df[
        ~df["id"].str.contains(
            r"PAGAMENTO|PAGTO|PAYMENT|PAGAMENTOS VALIDOS", case=False, regex=True, na=False
        )
    ].copy()


def calculate_kpis(df_filtered: pd.DataFrame, df_full: pd.DataFrame) -> dict:
    """Calculates core KPI metrics for the executive dashboard, netting genuine refunds and excluding payments."""
    if df_filtered.empty:
        return {
            "total_spent": 0.0,
            "gross_spent": 0.0,
            "total_refunds": 0.0,
            "total_tx": 0,
            "avg_tx": 0.0,
            "num_months": 0,
            "avg_monthly_spent": 0.0,
            "mom_delta_val": 0.0,
            "mom_delta_pct": 0.0,
            "latest_m_val": 0.0,
            "top_cat_name": "N/A",
            "top_cat_val": 0.0,
            "top_cat_pct": 0.0,
            "installment_spent": 0.0,
            "installment_pct": 0.0,
        }

    # Filter out payment settlement entries (e.g. Pagamentos Validos Normais)
    if "is_payment" in df_filtered.columns:
        df_effective = df_filtered[~df_filtered["is_payment"]].copy()
    else:
        df_effective = df_filtered[
            ~df_filtered["id"].str.contains(
                r"PAGAMENTO|PAGTO|PAYMENT|PAGAMENTOS VALIDOS", case=False, regex=True, na=False
            )
        ].copy()

    # Net spending = Gross purchases + Refunds (credits)
    total_spent = float(df_effective["cost"].sum())
    gross_spent = float(df_effective[df_effective["cost"] > 0]["cost"].sum())
    total_refunds = float(df_effective[df_effective["cost"] < 0]["cost"].sum())
    total_tx = len(df_effective[df_effective["cost"] > 0])
    avg_tx = total_spent / total_tx if total_tx > 0 else 0.0

    num_months = max(1, df_effective["year_month"].nunique())
    avg_monthly_spent = total_spent / num_months

    # Month-over-Month (MoM) calculations on full dataset excluding payments
    if "is_payment" in df_full.columns:
        df_full_eff = df_full[~df_full["is_payment"]].copy()
    else:
        df_full_eff = df_full[
            ~df_full["id"].str.contains(
                r"PAGAMENTO|PAGTO|PAYMENT|PAGAMENTOS VALIDOS", case=False, regex=True, na=False
            )
        ].copy()

    monthly_totals = df_full_eff.groupby("year_month")["cost"].sum().sort_index(ascending=False)
    mom_delta_pct = 0.0
    mom_delta_val = 0.0
    latest_m_val = 0.0
    if len(monthly_totals) >= 1:
        latest_m_val = float(monthly_totals.iloc[0])
    if len(monthly_totals) >= 2:
        latest_m = monthly_totals.iloc[0]
        prev_m = monthly_totals.iloc[1]
        mom_delta_val = float(latest_m - prev_m)
        mom_delta_pct = float((mom_delta_val / prev_m) * 100) if prev_m > 0 else 0.0

    # Top category
    cat_totals = df_effective.groupby("category_label")["cost"].sum().sort_values(ascending=False)
    top_cat_name = str(cat_totals.index[0]) if not cat_totals.empty else "N/A"
    top_cat_val = float(cat_totals.iloc[0]) if not cat_totals.empty else 0.0
    top_cat_pct = float(top_cat_val / total_spent * 100) if total_spent > 0 else 0.0

    # Installment share
    installment_spent = float(df_effective[df_effective["is_installment"]]["cost"].sum())
    installment_pct = float(installment_spent / total_spent * 100) if total_spent > 0 else 0.0

    return {
        "total_spent": total_spent,
        "gross_spent": gross_spent,
        "total_refunds": total_refunds,
        "total_tx": total_tx,
        "avg_tx": avg_tx,
        "num_months": num_months,
        "avg_monthly_spent": avg_monthly_spent,
        "mom_delta_val": mom_delta_val,
        "mom_delta_pct": mom_delta_pct,
        "latest_m_val": latest_m_val,
        "top_cat_name": top_cat_name,
        "top_cat_val": top_cat_val,
        "top_cat_pct": top_cat_pct,
        "installment_spent": installment_spent,
        "installment_pct": installment_pct,
    }


def get_monthly_grouped(df_expenses: pd.DataFrame, group_col: str = "year_month") -> pd.DataFrame:
    """Groups net expenses by the specified monthly grouping column and category (excluding payment settlements)."""
    if df_expenses.empty:
        return pd.DataFrame(columns=[group_col, "category_label", "category", "cost"])

    if "is_payment" in df_expenses.columns:
        df_eff = df_expenses[~df_expenses["is_payment"]].copy()
    else:
        df_eff = df_expenses[
            ~df_expenses["id"].str.contains(
                r"PAGAMENTO|PAGTO|PAYMENT|PAGAMENTOS VALIDOS", case=False, regex=True, na=False
            )
        ].copy()

    return (
        df_eff.groupby([group_col, "category_label", "category"])["cost"]
        .sum()
        .reset_index()
        .sort_values(by=[group_col, "cost"], ascending=[True, False])
    )


def get_top_merchants(df_expenses: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Calculates accumulated spending and count per merchant (excluding payments)."""
    if df_expenses.empty:
        return pd.DataFrame(columns=["id", "total_spent", "tx_count"])

    if "is_payment" in df_expenses.columns:
        df_eff = df_expenses[(~df_expenses["is_payment"]) & (df_expenses["cost"] > 0)].copy()
    else:
        df_eff = df_expenses[
            (
                ~df_expenses["id"].str.contains(
                    r"PAGAMENTO|PAGTO|PAYMENT|PAGAMENTOS VALIDOS", case=False, regex=True, na=False
                )
            )
            & (df_expenses["cost"] > 0)
        ].copy()

    agg = {"total_spent": ("cost", "sum"), "tx_count": ("cost", "count")}
    if "category" in df_eff.columns:
        # dominant category per merchant, used to color the merchant bars
        agg["category"] = (
            "category",
            lambda s: s.mode().iat[0] if not s.mode().empty else s.iloc[0],
        )

    return (
        df_eff.groupby("id")
        .agg(**agg)
        .reset_index()
        .sort_values(by="total_spent", ascending=True)
        .tail(top_n)
    )


def get_day_of_week_spending(df_expenses: pd.DataFrame) -> pd.DataFrame:
    """Calculates net spending grouped by day of the week in standard order."""
    order_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    if df_expenses.empty:
        return pd.DataFrame({"dia_semana": order_days, "cost": [0.0] * 7})

    if "is_payment" in df_expenses.columns:
        df_eff = df_expenses[~df_expenses["is_payment"]].copy()
    else:
        df_eff = df_expenses[
            ~df_expenses["id"].str.contains(
                r"PAGAMENTO|PAGTO|PAYMENT|PAGAMENTOS VALIDOS", case=False, regex=True, na=False
            )
        ].copy()

    df_eff["dia_semana"] = df_eff["date_buy"].dt.day_name()
    return df_eff.groupby("dia_semana")["cost"].sum().reindex(order_days).fillna(0.0).reset_index()


def get_future_installments_details(df_full: pd.DataFrame) -> pd.DataFrame:
    """Extracts all active installment commitments projected month-by-month."""
    if df_full.empty:
        return pd.DataFrame(
            columns=[
                "future_month",
                "id",
                "date_buy",
                "cost",
                "installment_display",
                "category_label",
                "category",
            ]
        )

    inst = df_full[df_full["total_installments"] > 1].copy()
    if inst.empty:
        return pd.DataFrame(
            columns=[
                "future_month",
                "id",
                "date_buy",
                "cost",
                "installment_display",
                "category_label",
                "category",
            ]
        )

    # Group by unique purchase identifier and take the latest billed record
    latest_inst = (
        inst.sort_values("date")
        .groupby(["id", "date_buy", "total_installments"])
        .last()
        .reset_index()
    )

    active_purchases = latest_inst[
        latest_inst["installment"] < latest_inst["total_installments"]
    ].copy()

    if active_purchases.empty:
        return pd.DataFrame(
            columns=[
                "future_month",
                "id",
                "date_buy",
                "cost",
                "installment_display",
                "category_label",
                "category",
            ]
        )

    max_invoice_date = df_full["date"].max()
    projections = []

    for _, row in active_purchases.iterrows():
        current_inst = int(row["installment"])
        total_inst = int(row["total_installments"])
        cost = float(row["cost"])
        remaining_installments = total_inst - current_inst

        for i in range(1, remaining_installments + 1):
            future_date = max_invoice_date + pd.DateOffset(months=i)
            future_month = future_date.strftime("%Y-%m")
            next_inst_num = current_inst + i
            projections.append(
                {
                    "future_month": future_month,
                    "id": row["id"],
                    "date_buy": row["date_buy"],
                    "cost": cost,
                    "installment_display": f"{next_inst_num}/{total_inst}",
                    "category_label": row.get("category_label", "Outros"),
                    "category": row.get("category", "not_found"),
                }
            )

    return pd.DataFrame(projections)


def get_future_installments_projection(df_full: pd.DataFrame) -> pd.DataFrame:
    """Projects future installment commitments aggregated by month and category."""
    df_details = get_future_installments_details(df_full)
    if df_details.empty:
        return pd.DataFrame(columns=["future_month", "cost", "category_label"])

    return (
        df_details.groupby(["future_month", "category_label"])["cost"]
        .sum()
        .reset_index()
        .sort_values("future_month")
    )


def get_next_month_commitment_metrics(
    df_full: pd.DataFrame, reference_limit: float = REFERENCE_BUDGET_LIMIT
) -> dict:
    """Calculates forecast KPI metrics for the upcoming month against a budget reference limit."""
    df_details = get_future_installments_details(df_full)

    if df_details.empty:
        return {
            "has_data": False,
            "next_month": "N/A",
            "next_month_cost": 0.0,
            "reference_limit": reference_limit,
            "diff_from_limit": reference_limit,
            "pct_of_limit": 0.0,
            "is_over_limit": False,
            "num_installments": 0,
            "total_future_debt": 0.0,
            "months_count": 0,
            "max_future_month": "N/A",
        }

    months_sorted = sorted(df_details["future_month"].unique())
    next_month = months_sorted[0]
    next_month_df = df_details[df_details["future_month"] == next_month]

    next_month_cost = float(next_month_df["cost"].sum())
    diff = next_month_cost - reference_limit
    pct = (next_month_cost / reference_limit) * 100.0 if reference_limit > 0 else 0.0
    is_over = next_month_cost > reference_limit
    num_inst = len(next_month_df)
    total_future_debt = float(df_details["cost"].sum())
    months_count = int(df_details["future_month"].nunique())
    max_future_month = str(df_details["future_month"].max())

    return {
        "has_data": True,
        "next_month": next_month,
        "next_month_cost": next_month_cost,
        "reference_limit": reference_limit,
        "diff_from_limit": diff,
        "pct_of_limit": pct,
        "is_over_limit": is_over,
        "num_installments": num_inst,
        "total_future_debt": total_future_debt,
        "months_count": months_count,
        "max_future_month": max_future_month,
    }


def get_moving_average(
    df_expenses: pd.DataFrame, group_col: str = "year_month", window: int = 3
) -> pd.DataFrame:
    """Calculates monthly net totals with a trailing moving average (excluding payment settlements)."""
    if df_expenses.empty:
        return pd.DataFrame(columns=[group_col, "cost", "moving_avg"])

    df_eff = _exclude_payments(df_expenses)
    monthly = (
        df_eff.groupby(group_col)["cost"]
        .sum()
        .reset_index()
        .sort_values(by=group_col, ascending=True)
        .reset_index(drop=True)
    )
    monthly["moving_avg"] = monthly["cost"].rolling(window=window, min_periods=1).mean()
    return monthly


def get_spending_trend(df_expenses: pd.DataFrame, group_col: str = "year_month") -> dict:
    """Fits a linear trend across monthly net totals and projects next period's spending."""
    monthly = get_moving_average(df_expenses, group_col=group_col, window=3)

    if monthly.empty:
        return {
            "has_data": False,
            "direction": "stable",
            "slope_per_month": 0.0,
            "current_avg": 0.0,
            "projected_next": 0.0,
            "moving_avg_df": monthly,
        }

    if len(monthly) < 2:
        last_val = float(monthly["cost"].iloc[-1])
        return {
            "has_data": True,
            "direction": "stable",
            "slope_per_month": 0.0,
            "current_avg": last_val,
            "projected_next": last_val,
            "moving_avg_df": monthly,
        }

    x = np.arange(len(monthly))
    y = monthly["cost"].to_numpy(dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    projected_next = max(0.0, float(slope * len(monthly) + intercept))

    avg_val = float(y.mean())
    rel_slope = (slope / abs(avg_val)) if avg_val else 0.0
    if rel_slope > 0.05:
        direction = "up"
    elif rel_slope < -0.05:
        direction = "down"
    else:
        direction = "stable"

    return {
        "has_data": True,
        "direction": direction,
        "slope_per_month": float(slope),
        "current_avg": float(monthly["moving_avg"].iloc[-1]),
        "projected_next": projected_next,
        "moving_avg_df": monthly,
    }


def get_year_over_year_comparison(df_full: pd.DataFrame) -> pd.DataFrame:
    """Compares net spending for each calendar month against the same month one year earlier."""
    columns = [
        "month_num",
        "month_name",
        "current_year",
        "current_val",
        "previous_year",
        "previous_val",
        "delta",
        "delta_pct",
    ]
    if df_full.empty or "year" not in df_full.columns or "month" not in df_full.columns:
        return pd.DataFrame(columns=columns)

    df_eff = _exclude_payments(df_full)
    if df_eff.empty:
        return pd.DataFrame(columns=columns)

    pivot = df_eff.groupby(["year", "month"])["cost"].sum().reset_index()
    years = sorted(pivot["year"].unique())
    if len(years) < 2:
        return pd.DataFrame(columns=columns)

    current_year, previous_year = years[-1], years[-2]
    cur = pivot[pivot["year"] == current_year].set_index("month")["cost"]
    prev = pivot[pivot["year"] == previous_year].set_index("month")["cost"]

    common_months = sorted(set(cur.index) & set(prev.index))
    if not common_months:
        return pd.DataFrame(columns=columns)

    month_names = {
        1: "Jan",
        2: "Feb",
        3: "Mar",
        4: "Apr",
        5: "May",
        6: "Jun",
        7: "Jul",
        8: "Aug",
        9: "Sep",
        10: "Oct",
        11: "Nov",
        12: "Dec",
    }

    rows = []
    for m in common_months:
        cur_val = float(cur.loc[m])
        prev_val = float(prev.loc[m])
        delta = cur_val - prev_val
        delta_pct = (delta / prev_val * 100) if prev_val != 0 else 0.0
        rows.append(
            {
                "month_num": m,
                "month_name": month_names.get(int(m), str(m)),
                "current_year": int(current_year),
                "current_val": cur_val,
                "previous_year": int(previous_year),
                "previous_val": prev_val,
                "delta": delta,
                "delta_pct": delta_pct,
            }
        )
    return pd.DataFrame(rows).sort_values("month_num").reset_index(drop=True)


def get_period_over_period_comparison(df_full: pd.DataFrame, selected_months: list) -> dict:
    """Compares total & category-level net spending of the selected period against the immediately preceding period of equal length."""
    empty_result = {
        "has_data": False,
        "current_months": [],
        "previous_months": [],
        "current_total": 0.0,
        "previous_total": 0.0,
        "delta": 0.0,
        "delta_pct": 0.0,
        "by_category": pd.DataFrame(
            columns=["category_label", "current", "previous", "delta", "delta_pct"]
        ),
    }
    if df_full.empty or not selected_months:
        return empty_result

    df_eff = _exclude_payments(df_full)
    all_months = sorted(df_eff["year_month"].dropna().unique().tolist())
    current_months = sorted(set(selected_months) & set(all_months))
    if not current_months:
        return empty_result

    n = len(current_months)
    earliest_idx = all_months.index(current_months[0])
    previous_months = all_months[max(0, earliest_idx - n) : earliest_idx]

    if not previous_months:
        return empty_result

    df_current = df_eff[df_eff["year_month"].isin(current_months)]
    df_previous = df_eff[df_eff["year_month"].isin(previous_months)]

    current_total = float(df_current["cost"].sum())
    previous_total = float(df_previous["cost"].sum())
    delta = current_total - previous_total
    delta_pct = (delta / previous_total * 100) if previous_total != 0 else 0.0

    cur_cat = df_current.groupby("category_label")["cost"].sum()
    prev_cat = df_previous.groupby("category_label")["cost"].sum()
    all_cats = sorted(set(cur_cat.index) | set(prev_cat.index))

    rows = []
    for c in all_cats:
        cv = float(cur_cat.get(c, 0.0))
        pv = float(prev_cat.get(c, 0.0))
        d = cv - pv
        dp = (d / pv * 100) if pv != 0 else (100.0 if cv > 0 else 0.0)
        rows.append(
            {"category_label": c, "current": cv, "previous": pv, "delta": d, "delta_pct": dp}
        )

    by_category = pd.DataFrame(rows).sort_values("current", ascending=False).reset_index(drop=True)

    return {
        "has_data": True,
        "current_months": current_months,
        "previous_months": previous_months,
        "current_total": current_total,
        "previous_total": previous_total,
        "delta": delta,
        "delta_pct": delta_pct,
        "by_category": by_category,
    }


def get_spending_anomalies(
    df_expenses: pd.DataFrame,
    z_threshold: float = ANOMALY_Z_THRESHOLD,
    min_category_tx: int = ANOMALY_MIN_CATEGORY_TX,
) -> pd.DataFrame:
    """Flags individual purchase transactions that deviate significantly from their category's typical spending pattern (z-score)."""
    columns = ["date_buy", "id", "cost", "category_label", "category", "z_score", "category_avg"]
    if df_expenses.empty:
        return pd.DataFrame(columns=columns)

    df_eff = _exclude_payments(df_expenses)
    df_eff = df_eff[df_eff["cost"] > 0].copy()
    if df_eff.empty:
        return pd.DataFrame(columns=columns)

    flagged = []
    for _cat, group in df_eff.groupby("category"):
        if len(group) < min_category_tx:
            continue
        mean = group["cost"].mean()
        std = group["cost"].std(ddof=0)
        if not std:
            continue
        z_scores = (group["cost"] - mean) / std
        mask = z_scores > z_threshold
        if not mask.any():
            continue
        outliers = group[mask].copy()
        outliers["z_score"] = z_scores[mask]
        outliers["category_avg"] = mean
        flagged.append(outliers)

    if not flagged:
        return pd.DataFrame(columns=columns)

    df_flagged = pd.concat(flagged)
    return df_flagged[columns].sort_values("z_score", ascending=False).reset_index(drop=True)


def get_recurring_merchants(
    df_full: pd.DataFrame,
    min_months: int = RECURRING_MIN_MONTHS,
    max_cv: float = RECURRING_MAX_CV,
) -> pd.DataFrame:
    """Detects likely recurring subscriptions/fixed costs: merchants billed consistently across multiple distinct months."""
    columns = [
        "id",
        "category_label",
        "months_count",
        "avg_monthly_cost",
        "last_amount",
        "last_month",
        "status",
    ]
    if df_full.empty:
        return pd.DataFrame(columns=columns)

    df_eff = _exclude_payments(df_full)
    df_eff = df_eff[df_eff["cost"] > 0].copy()
    if df_eff.empty:
        return pd.DataFrame(columns=columns)

    monthly_merchant = (
        df_eff.groupby(["id", "year_month"])
        .agg(cost=("cost", "sum"), category_label=("category_label", "first"))
        .reset_index()
    )

    rows = []
    for merchant_id, group in monthly_merchant.groupby("id"):
        months_count = group["year_month"].nunique()
        if months_count < min_months:
            continue
        mean_cost = group["cost"].mean()
        std_cost = group["cost"].std(ddof=0)
        cv = (std_cost / mean_cost) if mean_cost else 0.0
        if cv > max_cv:
            continue

        group_sorted = group.sort_values("year_month")
        last_row = group_sorted.iloc[-1]
        last_amount = float(last_row["cost"])
        last_month = str(last_row["year_month"])

        diff_pct = ((last_amount - mean_cost) / mean_cost * 100) if mean_cost else 0.0
        if diff_pct > 10:
            status = "Increased"
        elif diff_pct < -10:
            status = "Decreased"
        else:
            status = "Stable"

        rows.append(
            {
                "id": merchant_id,
                "category_label": group_sorted["category_label"].iloc[-1],
                "months_count": int(months_count),
                "avg_monthly_cost": float(mean_cost),
                "last_amount": last_amount,
                "last_month": last_month,
                "status": status,
            }
        )

    if not rows:
        return pd.DataFrame(columns=columns)

    return (
        pd.DataFrame(rows).sort_values("avg_monthly_cost", ascending=False).reset_index(drop=True)
    )


def get_month_pace_projection(df_full: pd.DataFrame, lookback_months: int = 3) -> dict:
    """Projects the current invoice month's total from elapsed-day pace, compared against the
    trailing average of the prior `lookback_months` completed months."""
    empty_result = {
        "has_data": False,
        "current_month": "N/A",
        "days_elapsed": 0,
        "days_in_month": 0,
        "mtd_spend": 0.0,
        "projected_total": 0.0,
        "historical_avg": 0.0,
        "pace_delta_pct": 0.0,
        "status": "normal",
    }
    if df_full.empty or "year_month" not in df_full.columns:
        return empty_result

    df_eff = _exclude_payments(df_full)
    if df_eff.empty:
        return empty_result

    monthly = df_eff.groupby("year_month")["cost"].sum().sort_index()
    if monthly.empty:
        return empty_result

    current_month = monthly.index[-1]
    mtd_spend = float(monthly.iloc[-1])

    max_date = df_eff["date"].max()
    days_in_month = calendar.monthrange(max_date.year, max_date.month)[1]
    days_elapsed = max_date.day
    if days_elapsed <= 0:
        return empty_result

    projected_total = mtd_spend / days_elapsed * days_in_month

    prior_months = monthly.iloc[:-1].tail(lookback_months)
    historical_avg = float(prior_months.mean()) if not prior_months.empty else 0.0
    pace_delta_pct = (
        (projected_total - historical_avg) / historical_avg * 100 if historical_avg > 0 else 0.0
    )

    if pace_delta_pct > 15:
        status = "hot"
    elif pace_delta_pct < -15:
        status = "cold"
    else:
        status = "normal"

    return {
        "has_data": True,
        "current_month": str(current_month),
        "days_elapsed": int(days_elapsed),
        "days_in_month": int(days_in_month),
        "mtd_spend": mtd_spend,
        "projected_total": float(projected_total),
        "historical_avg": historical_avg,
        "pace_delta_pct": float(pace_delta_pct),
        "status": status,
    }


def get_category_momentum(df_full: pd.DataFrame, window: int = 3) -> pd.DataFrame:
    """Flags categories whose net spend moved consistently up or down over the trailing `window`
    months (unlike a single-month MoM comparison, which can hide a multi-month trend)."""
    columns = [
        "category",
        "category_label",
        "months_available",
        "direction",
        "streak",
        "slope_per_month",
        "last_month_value",
        "pct_change_over_window",
    ]
    if df_full.empty:
        return pd.DataFrame(columns=columns)

    df_eff = _exclude_payments(df_full)
    df_eff = df_eff[df_eff["cost"] > 0].copy()
    if df_eff.empty:
        return pd.DataFrame(columns=columns)

    monthly_cat = (
        df_eff.groupby(["category", "category_label", "year_month"])["cost"].sum().reset_index()
    )

    rows = []
    for (cat, cat_label), group in monthly_cat.groupby(["category", "category_label"]):
        group_sorted = group.sort_values("year_month")
        months_available = len(group_sorted)
        if months_available < window:
            continue

        values = group_sorted.tail(window)["cost"].to_numpy(dtype=float)
        deltas = values[1:] - values[:-1]

        if (deltas > 0).all():
            streak, base_direction = window, "rising"
        elif (deltas < 0).all():
            streak, base_direction = window, "falling"
        else:
            streak, base_direction = 0, None

        x = np.arange(len(values))
        slope, _intercept = np.polyfit(x, values, 1)
        avg_val = float(values.mean())
        rel_slope = (slope / abs(avg_val)) if avg_val else 0.0

        if base_direction is not None:
            direction = base_direction
        elif rel_slope > 0.05:
            direction = "rising"
        elif rel_slope < -0.05:
            direction = "falling"
        else:
            direction = "stable"

        first_val, last_val = float(values[0]), float(values[-1])
        pct_change = ((last_val - first_val) / first_val * 100) if first_val else 0.0

        rows.append(
            {
                "category": cat,
                "category_label": cat_label,
                "months_available": int(months_available),
                "direction": direction,
                "streak": int(streak),
                "slope_per_month": float(slope),
                "last_month_value": last_val,
                "pct_change_over_window": float(pct_change),
            }
        )

    if not rows:
        return pd.DataFrame(columns=columns)

    return (
        pd.DataFrame(rows)
        .sort_values("pct_change_over_window", ascending=False)
        .reset_index(drop=True)
    )


def get_financial_health_score(
    df_full: pd.DataFrame, reference_limit: float = REFERENCE_BUDGET_LIMIT
) -> dict:
    """Composite 0-100 financial health score blending installment burden, anomaly rate, next-month
    budget proximity, and month-over-month spend volatility, each weighted sub-score 0-100."""
    empty_result = {
        "has_data": False,
        "score": 0,
        "rating": "N/A",
        "components": {},
        "top_factor": "N/A",
    }
    if df_full.empty:
        return empty_result

    kpis = calculate_kpis(df_full, df_full)
    if kpis["total_spent"] <= 0:
        return empty_result

    df_eff = _exclude_payments(df_full)

    installment_score = max(0.0, 100.0 - (kpis["installment_pct"] / 60.0) * 100.0)

    anomalies = get_spending_anomalies(
        df_eff, z_threshold=ANOMALY_Z_THRESHOLD, min_category_tx=ANOMALY_MIN_CATEGORY_TX
    )
    anomaly_score = max(0.0, 100.0 - (len(anomalies) / 5.0) * 100.0)

    next_metrics = get_next_month_commitment_metrics(df_full, reference_limit=reference_limit)
    if next_metrics["has_data"] and reference_limit > 0:
        budget_score = max(0.0, 100.0 - next_metrics["pct_of_limit"])
    else:
        budget_score = 100.0

    volatility_score = max(0.0, 100.0 - min(abs(kpis["mom_delta_pct"]), 100.0))

    components = {
        "installment_burden": round(installment_score, 1),
        "anomalies": round(anomaly_score, 1),
        "budget_proximity": round(budget_score, 1),
        "spend_volatility": round(volatility_score, 1),
    }

    score = round(
        installment_score * 0.3
        + anomaly_score * 0.25
        + budget_score * 0.25
        + volatility_score * 0.2
    )

    if score >= 80:
        rating = "Excellent"
    elif score >= 60:
        rating = "Good"
    elif score >= 40:
        rating = "Fair"
    else:
        rating = "At Risk"

    top_factor = min(components, key=components.get)

    return {
        "has_data": True,
        "score": int(score),
        "rating": rating,
        "components": components,
        "top_factor": top_factor,
    }


def get_merchant_frequency_change(
    df_full: pd.DataFrame,
    recent_months: int = 2,
    baseline_months: int = 6,
    min_baseline_tx: int = 3,
) -> pd.DataFrame:
    """Detects merchants whose recent transaction frequency deviates notably from their historical
    baseline pace — distinct from get_recurring_merchants, which detects stable fixed costs rather
    than a change in how often a merchant is used."""
    columns = [
        "id",
        "category_label",
        "recent_monthly_rate",
        "baseline_monthly_rate",
        "change_pct",
        "direction",
    ]
    if df_full.empty:
        return pd.DataFrame(columns=columns)

    df_eff = _exclude_payments(df_full)
    df_eff = df_eff[df_eff["cost"] > 0].copy()
    if df_eff.empty:
        return pd.DataFrame(columns=columns)

    all_months = sorted(df_eff["year_month"].dropna().unique().tolist())
    if len(all_months) < recent_months + 1:
        return pd.DataFrame(columns=columns)

    recent_set = set(all_months[-recent_months:])
    baseline_candidates = all_months[:-recent_months]
    baseline_set = set(baseline_candidates[-baseline_months:])
    if not baseline_set:
        return pd.DataFrame(columns=columns)

    df_recent = df_eff[df_eff["year_month"].isin(recent_set)]
    df_baseline = df_eff[df_eff["year_month"].isin(baseline_set)]

    recent_counts = df_recent.groupby("id").size()
    baseline_counts = df_baseline.groupby("id").size()
    cat_lookup = df_eff.groupby("id")["category_label"].first()

    rows = []
    for merchant_id, baseline_tx in baseline_counts.items():
        if baseline_tx < min_baseline_tx:
            continue
        baseline_rate = baseline_tx / len(baseline_set)
        if baseline_rate <= 0:
            continue
        recent_tx = int(recent_counts.get(merchant_id, 0))
        recent_rate = recent_tx / recent_months

        change_pct = (recent_rate - baseline_rate) / baseline_rate * 100
        if abs(change_pct) < 50:
            continue

        rows.append(
            {
                "id": merchant_id,
                "category_label": cat_lookup.get(merchant_id, "Uncategorized"),
                "recent_monthly_rate": float(recent_rate),
                "baseline_monthly_rate": float(baseline_rate),
                "change_pct": float(change_pct),
                "direction": "increased" if change_pct > 0 else "decreased",
            }
        )

    if not rows:
        return pd.DataFrame(columns=columns)

    return (
        pd.DataFrame(rows)
        .sort_values("change_pct", ascending=False, key=abs)
        .reset_index(drop=True)
    )
