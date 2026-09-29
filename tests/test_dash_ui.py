"""Dash frontend: the app builds without a DB and every tab view renders from a Silver-shaped frame."""

import random

import pandas as pd
import pytest

from src.expenses.config import CATEGORY_CONFIG
from src.expenses.dash_ui import create_app
from src.expenses.dash_ui.tabs import (
    build_category_view,
    build_dashboard_view,
    build_reports_view,
    build_trends_view,
    category_options,
    export_csv,
)
from src.expenses.database import _shape_silver_frame
from src.expenses.filters import DEFAULT_FILTERS, apply_filters
from src.expenses.ui.charts import chart_context
from src.expenses.ui.figures import build_monthly_evolution_figure


@pytest.fixture(scope="module")
def df_full():
    rng = random.Random(7)
    cats = list(CATEGORY_CONFIG)
    rows = []
    for month in pd.period_range("2025-01", "2026-09", freq="M"):
        invoice = month.to_timestamp() + pd.Timedelta(days=4)
        for _ in range(30):
            total = rng.choice([0, 0, 3, 6])
            rows.append(
                {
                    "date": invoice,
                    "date_buy": invoice - pd.Timedelta(days=rng.randint(3, 28)),
                    "id": f"SHOP {rng.randint(1, 6)}",
                    "cost": round(rng.uniform(15, 400), 2),
                    "installment": rng.randint(1, total) if total else 0,
                    "total_installments": total,
                    "category": rng.choice(cats),
                    "source_debt": "CARD A",
                }
            )
        rows.append({**rows[-1], "id": "PAGAMENTO FATURA", "cost": -2000.0, "category": "food"})
    return _shape_silver_frame(pd.DataFrame(rows))


def test_create_app_without_database():
    app = create_app(data_loader=lambda: pd.DataFrame())
    assert callable(app.layout)


def test_views_render_with_data(df_full):
    df = apply_filters(df_full, DEFAULT_FILTERS)
    assert build_dashboard_view(df, df_full)
    assert build_trends_view(df, df_full)
    assert build_reports_view(df, df_full, 5000.0)
    options = category_options(df)
    assert options and (options[-1]["value"] == "not_found" or "not_found" not in str(options))
    assert build_category_view(df, options[0]["value"])


def test_views_handle_empty_frame(df_full):
    empty = df_full.iloc[0:0]
    for view in (
        build_dashboard_view(empty, df_full),
        build_trends_view(empty, df_full),
        build_reports_view(empty, df_full),
        build_category_view(empty, None),
    ):
        assert len(view) == 1


def test_export_csv_roundtrip(df_full):
    name, content = export_csv(df_full.head(3))
    assert name.startswith("expenses_report_") and name.endswith(".csv")
    assert content.count("\n") == 4


def test_chart_context_overrides_theme_and_amounts(df_full):
    df = df_full[~df_full["is_payment"]]
    with chart_context(theme_base="light", hide_amounts=True):
        fig = build_monthly_evolution_figure(df)
    assert fig.layout.font.color == "#1F2933"
    assert not fig.data[-2].text
