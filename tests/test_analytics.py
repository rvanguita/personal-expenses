import pandas as pd

from src.expenses.analytics import (
    calculate_kpis,
    get_category_momentum,
    get_day_of_week_spending,
    get_financial_health_score,
    get_future_installments_details,
    get_future_installments_projection,
    get_merchant_frequency_change,
    get_month_pace_projection,
    get_monthly_grouped,
    get_moving_average,
    get_next_month_commitment_metrics,
    get_period_over_period_comparison,
    get_recurring_merchants,
    get_spending_anomalies,
    get_spending_trend,
    get_top_merchants,
    get_year_over_year_comparison,
)


def test_calculate_kpis(sample_expenses_df):
    kpis = calculate_kpis(sample_expenses_df, sample_expenses_df)
    assert kpis["total_spent"] == 830.50
    assert kpis["total_tx"] == 4
    assert kpis["num_months"] == 2
    assert kpis["top_cat_name"] == "Shopping"
    assert kpis["installment_spent"] == 400.00
    assert round(kpis["installment_pct"], 2) == round(400.0 / 830.50 * 100, 2)


def test_get_monthly_grouped(sample_expenses_df):
    df_grouped = get_monthly_grouped(sample_expenses_df)
    assert not df_grouped.empty
    assert "year_month" in df_grouped.columns
    assert "category_label" in df_grouped.columns
    assert "cost" in df_grouped.columns


def test_get_top_merchants(sample_expenses_df):
    top_df = get_top_merchants(sample_expenses_df, top_n=2)
    assert len(top_df) == 2
    assert "DEMO STORE" in top_df["id"].values
    # dominant category carried through for bar coloring
    assert "category" in top_df.columns
    assert top_df.set_index("id").loc["DEMO STORE", "category"] == "shopping"


def test_get_day_of_week_spending(sample_expenses_df):
    days_df = get_day_of_week_spending(sample_expenses_df)
    assert len(days_df) == 7
    assert "Monday" in days_df["dia_semana"].values


def test_get_future_installments_projection(sample_expenses_df):
    projection_df = get_future_installments_projection(sample_expenses_df)
    assert not projection_df.empty
    assert "2026-03" in projection_df["future_month"].values


def test_get_future_installments_details(sample_expenses_df):
    details_df = get_future_installments_details(sample_expenses_df)
    assert not details_df.empty
    assert "DEMO STORE" in details_df["id"].values
    assert "future_month" in details_df.columns
    assert "installment_display" in details_df.columns


def test_get_next_month_commitment_metrics(sample_expenses_df):
    metrics = get_next_month_commitment_metrics(sample_expenses_df, reference_limit=5000.0)
    assert metrics["has_data"] is True
    assert metrics["next_month"] == "2026-03"
    assert metrics["next_month_cost"] == 400.00
    assert metrics["reference_limit"] == 5000.0
    assert metrics["pct_of_limit"] == 8.0
    assert metrics["is_over_limit"] is False
    assert metrics["total_future_debt"] == 800.00
    assert metrics["months_count"] == 2
    assert metrics["max_future_month"] == "2026-04"


def test_calculate_kpis_with_refunds_and_payments(sample_expenses_df):
    df_extra = pd.DataFrame(
        [
            {
                "date": pd.to_datetime("2026-07-05"),
                "date_buy": pd.to_datetime("2026-06-15"),
                "id": "PAGAMENTOS VALIDOS NORMAIS",
                "source_debt": "CARDHOLDER_A",
                "cost": -5000.00,
                "installment": 0,
                "total_installments": 0,
                "category": "not_found",
                "category_label": "Uncategorized",
                "is_installment": False,
                "is_payment": True,
                "is_refund": False,
                "year_month": "2026-07",
            },
            {
                "date": pd.to_datetime("2026-07-05"),
                "date_buy": pd.to_datetime("2026-06-16"),
                "id": "ALIEXPRESS REFUND",
                "source_debt": "CARDHOLDER_A",
                "cost": -30.00,
                "installment": 0,
                "total_installments": 0,
                "category": "shopping",
                "category_label": "Shopping",
                "is_installment": False,
                "is_payment": False,
                "is_refund": True,
                "year_month": "2026-07",
            },
            {
                "date": pd.to_datetime("2026-07-05"),
                "date_buy": pd.to_datetime("2026-06-17"),
                "id": "DEMO TRANSIT RIDE",
                "source_debt": "CARDHOLDER_A",
                "cost": 100.00,
                "installment": 0,
                "total_installments": 0,
                "category": "transport",
                "category_label": "Transportation",
                "is_installment": False,
                "is_payment": False,
                "is_refund": False,
                "year_month": "2026-07",
            },
        ]
    )
    kpis = calculate_kpis(df_extra, df_extra)
    # Total spent must be 100 - 30 = 70 (excluding the -5000 payment)
    assert kpis["total_spent"] == 70.00
    assert kpis["gross_spent"] == 100.00
    assert kpis["total_refunds"] == -30.00


def test_get_moving_average(sample_expenses_df):
    ma_df = get_moving_average(sample_expenses_df)
    assert not ma_df.empty
    assert "moving_avg" in ma_df.columns
    assert list(ma_df["year_month"]) == ["2026-01", "2026-02"]
    assert ma_df.iloc[0]["moving_avg"] == ma_df.iloc[0]["cost"]


def test_get_spending_trend(sample_expenses_df):
    trend = get_spending_trend(sample_expenses_df)
    assert trend["has_data"] is True
    assert trend["direction"] in {"up", "down", "stable"}
    assert trend["projected_next"] >= 0.0


def test_get_spending_trend_empty():
    trend = get_spending_trend(pd.DataFrame())
    assert trend["has_data"] is False
    assert trend["direction"] == "stable"


def test_get_period_over_period_comparison(sample_expenses_df):
    result = get_period_over_period_comparison(sample_expenses_df, ["2026-02"])
    assert result["has_data"] is True
    assert result["current_months"] == ["2026-02"]
    assert result["previous_months"] == ["2026-01"]
    assert result["current_total"] == 50.00
    assert round(result["previous_total"], 2) == 780.50
    assert not result["by_category"].empty


def test_get_period_over_period_comparison_no_prior_history(sample_expenses_df):
    result = get_period_over_period_comparison(sample_expenses_df, ["2026-01"])
    assert result["has_data"] is False


def test_get_year_over_year_comparison_missing_columns(sample_expenses_df):
    # sample_expenses_df has no 'year'/'month' columns, so the comparison must degrade gracefully.
    yoy = get_year_over_year_comparison(sample_expenses_df)
    assert yoy.empty


def test_get_year_over_year_comparison_with_data():
    df_extra = pd.DataFrame(
        [
            {"year": 2025, "month": 1, "cost": 1000.0, "is_payment": False},
            {"year": 2025, "month": 2, "cost": 800.0, "is_payment": False},
            {"year": 2026, "month": 1, "cost": 1200.0, "is_payment": False},
            {"year": 2026, "month": 2, "cost": 900.0, "is_payment": False},
        ]
    )
    yoy = get_year_over_year_comparison(df_extra)
    assert len(yoy) == 2
    jan_row = yoy[yoy["month_num"] == 1].iloc[0]
    assert jan_row["current_year"] == 2026
    assert jan_row["previous_year"] == 2025
    assert jan_row["current_val"] == 1200.0
    assert jan_row["previous_val"] == 1000.0
    assert round(jan_row["delta_pct"], 1) == 20.0


def test_get_recurring_merchants_detects_subscription():
    rows = [
        {
            "id": "DEMO STREAMING",
            "year_month": ym,
            "cost": 39.90,
            "category_label": "Services & Subscriptions",
            "is_payment": False,
        }
        for ym in ["2026-01", "2026-02", "2026-03"]
    ]
    rows.append(
        {
            "id": "EXAMPLE STORE",
            "year_month": "2026-01",
            "cost": 150.00,
            "category_label": "Shopping",
            "is_payment": False,
        }
    )
    df_extra = pd.DataFrame(rows)
    recurring = get_recurring_merchants(df_extra, min_months=3, max_cv=0.35)
    assert len(recurring) == 1
    assert recurring.iloc[0]["id"] == "DEMO STREAMING"
    assert recurring.iloc[0]["months_count"] == 3
    assert recurring.iloc[0]["status"] == "Stable"


def test_get_recurring_merchants_empty():
    recurring = get_recurring_merchants(pd.DataFrame())
    assert recurring.empty
    assert "status" in recurring.columns


def test_get_spending_anomalies_flags_outlier():
    base_date = pd.Timestamp("2026-01-05")
    rows = [
        {
            "id": f"MERCHANT_{i}",
            "date_buy": base_date,
            "cost": float(cost),
            "category": "shopping",
            "category_label": "Shopping",
            "is_payment": False,
        }
        for i, cost in enumerate([100, 101, 99, 100, 100, 98, 102, 9000])
    ]
    df_extra = pd.DataFrame(rows)
    anomalies = get_spending_anomalies(df_extra, z_threshold=2.5, min_category_tx=5)
    assert len(anomalies) == 1
    assert anomalies.iloc[0]["cost"] == 9000.0


def test_get_spending_anomalies_empty(sample_expenses_df):
    # Too few transactions per category to establish a statistical pattern.
    anomalies = get_spending_anomalies(sample_expenses_df, min_category_tx=5)
    assert anomalies.empty


def test_get_month_pace_projection(sample_expenses_df):
    pace = get_month_pace_projection(sample_expenses_df)
    assert pace["has_data"] is True
    assert pace["current_month"] == "2026-02"
    assert pace["days_in_month"] == 28
    assert pace["days_elapsed"] == 5
    assert pace["mtd_spend"] == 50.00
    assert round(pace["projected_total"], 2) == 280.00
    assert pace["historical_avg"] == 780.50
    assert pace["status"] == "cold"


def test_get_month_pace_projection_empty():
    pace = get_month_pace_projection(pd.DataFrame())
    assert pace["has_data"] is False
    assert pace["status"] == "normal"


def test_get_category_momentum_detects_rising_trend():
    rows = [
        {
            "category": "shopping",
            "category_label": "Shopping",
            "year_month": ym,
            "cost": cost,
            "is_payment": False,
        }
        for ym, cost in zip(["2026-01", "2026-02", "2026-03"], [100.0, 150.0, 200.0], strict=True)
    ]
    rows.append(
        {
            "category": "food",
            "category_label": "Food & Dining",
            "year_month": "2026-01",
            "cost": 50.0,
            "is_payment": False,
        }
    )
    df_extra = pd.DataFrame(rows)
    momentum = get_category_momentum(df_extra, window=3)
    assert len(momentum) == 1
    shopping_row = momentum.iloc[0]
    assert shopping_row["category"] == "shopping"
    assert shopping_row["direction"] == "rising"
    assert shopping_row["streak"] == 3
    assert shopping_row["months_available"] == 3


def test_get_category_momentum_empty():
    momentum = get_category_momentum(pd.DataFrame())
    assert momentum.empty
    assert "direction" in momentum.columns


def _build_health_score_rows(is_installment: bool):
    rows = []
    for ym, date_str in [("2026-01", "2026-01-05"), ("2026-02", "2026-02-05")]:
        for i in range(3):
            rows.append(
                {
                    "date": pd.Timestamp(date_str),
                    "date_buy": pd.Timestamp(date_str),
                    "id": f"MERCHANT_{i}",
                    "cost": 100.0,
                    "installment": 1 if is_installment else 0,
                    "total_installments": 3 if is_installment else 0,
                    "category": "groceries",
                    "category_label": "Groceries",
                    "year_month": ym,
                    "is_installment": is_installment,
                    "is_payment": False,
                }
            )
    return pd.DataFrame(rows)


def test_get_financial_health_score_clean_data():
    health = get_financial_health_score(_build_health_score_rows(is_installment=False))
    assert health["has_data"] is True
    assert health["score"] >= 80
    assert health["rating"] == "Excellent"


def test_get_financial_health_score_penalizes_installment_burden():
    health = get_financial_health_score(_build_health_score_rows(is_installment=True))
    assert health["has_data"] is True
    assert health["components"]["installment_burden"] < 100
    assert health["score"] < 100


def test_get_financial_health_score_empty():
    health = get_financial_health_score(pd.DataFrame())
    assert health["has_data"] is False
    assert health["score"] == 0


def test_get_merchant_frequency_change_detects_increase():
    baseline_months = ["2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12"]
    rows = [
        {
            "id": "IFOOD",
            "year_month": ym,
            "cost": 40.0,
            "category_label": "Food & Dining",
            "is_payment": False,
        }
        for ym in baseline_months
    ]
    for ym in ["2026-01", "2026-02"]:
        rows.extend(
            {
                "id": "IFOOD",
                "year_month": ym,
                "cost": 40.0,
                "category_label": "Food & Dining",
                "is_payment": False,
            }
            for _ in range(3)
        )
    df_extra = pd.DataFrame(rows)
    freq = get_merchant_frequency_change(
        df_extra, recent_months=2, baseline_months=6, min_baseline_tx=3
    )
    assert len(freq) == 1
    row = freq.iloc[0]
    assert row["id"] == "IFOOD"
    assert row["direction"] == "increased"
    assert round(row["baseline_monthly_rate"], 2) == 1.0
    assert round(row["recent_monthly_rate"], 2) == 3.0
    assert round(row["change_pct"], 1) == 200.0


def test_get_merchant_frequency_change_insufficient_baseline():
    rows = [
        {
            "id": "NEW_STORE",
            "year_month": ym,
            "cost": 20.0,
            "category_label": "Shopping",
            "is_payment": False,
        }
        for ym in ["2026-01", "2026-02"]
    ]
    freq = get_merchant_frequency_change(pd.DataFrame(rows))
    assert freq.empty
