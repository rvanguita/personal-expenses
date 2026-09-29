import io

import pandas as pd
import pytest


@pytest.fixture
def sample_raw_csv_content():
    return """Data;Estabelecimento;Portador;Valor;Parcela
01/12/2025;EXAMPLE MARKET ONLINE;CARDHOLDER_A;R$ 150,00;-
01/12/2025;SAMPLE GROCERY;CARDHOLDER_A;R$ 230,50;-
05/12/2025;DEMO STORE;CARDHOLDER_A;R$ 1.200,00;1 de 3
10/12/2025;DEMO TRANSIT RIDE;CARDHOLDER_A;R$ 35,40;-
15/12/2025;PAGAMENTO FATURA;CARDHOLDER_A;-R$ 1.500,00;-
"""


@pytest.fixture
def sample_csv_file(sample_raw_csv_content):
    f = io.StringIO(sample_raw_csv_content)
    f.name = "Invoice2026-01-05.csv"
    return f


@pytest.fixture
def sample_expenses_df():
    data = [
        {
            "date": pd.Timestamp("2026-01-05"),
            "date_buy": pd.Timestamp("2025-12-01"),
            "id": "EXAMPLE MARKET ONLINE",
            "cost": 150.00,
            "installment": 0,
            "total_installments": 0,
            "category": "shopping",
            "category_label": "Shopping",
            "year_month": "2026-01",
            "is_installment": False,
        },
        {
            "date": pd.Timestamp("2026-01-05"),
            "date_buy": pd.Timestamp("2025-12-01"),
            "id": "SAMPLE GROCERY",
            "cost": 230.50,
            "installment": 0,
            "total_installments": 0,
            "category": "groceries",
            "category_label": "Groceries",
            "year_month": "2026-01",
            "is_installment": False,
        },
        {
            "date": pd.Timestamp("2026-01-05"),
            "date_buy": pd.Timestamp("2025-12-05"),
            "id": "DEMO STORE",
            "cost": 400.00,
            "installment": 1,
            "total_installments": 3,
            "category": "shopping",
            "category_label": "Shopping",
            "year_month": "2026-01",
            "is_installment": True,
        },
        {
            "date": pd.Timestamp("2026-02-05"),
            "date_buy": pd.Timestamp("2026-01-10"),
            "id": "DEMO TRANSIT RIDE",
            "cost": 50.00,
            "installment": 0,
            "total_installments": 0,
            "category": "transport",
            "category_label": "Transportation",
            "year_month": "2026-02",
            "is_installment": False,
        },
    ]
    return pd.DataFrame(data)


@pytest.fixture(scope="session")
def silver_history_df():
    """~21 months of synthetic Silver rows (installments, refunds, payments, uncategorized),
    shaped by the real ``_shape_silver_frame`` so every derived column the UI needs exists."""
    import random

    from src.expenses.config import CATEGORY_CONFIG
    from src.expenses.database import _shape_silver_frame

    rng = random.Random(7)
    categories = list(CATEGORY_CONFIG)
    rows = []
    for month in pd.period_range("2025-01", "2026-09", freq="M"):
        invoice = month.to_timestamp() + pd.Timedelta(days=4)
        for _ in range(30):
            total = rng.choice([0, 0, 3, 6])
            category = rng.choice(categories)
            rows.append(
                {
                    "date": invoice,
                    "date_buy": invoice - pd.Timedelta(days=rng.randint(3, 28)),
                    "id": f"{category.upper()} SHOP {rng.randint(1, 3)}",
                    "cost": round(rng.uniform(15, 400), 2),
                    "installment": rng.randint(1, total) if total else 0,
                    "total_installments": total,
                    "category": category,
                    "source_debt": rng.choice(["CARDHOLDER_A", "CARDHOLDER_B"]),
                }
            )
        base = {"date": invoice, "date_buy": invoice, "installment": 0, "total_installments": 0}
        rows += [
            {
                **base,
                "id": "DEMO STREAMING",
                "cost": 39.9,
                "category": "services",
                "source_debt": "CARDHOLDER_A",
            },
            {
                **base,
                "id": "PAGAMENTO FATURA",
                "cost": -3000.0,
                "category": "not_found",
                "source_debt": "CARDHOLDER_A",
            },
            {
                **base,
                "id": "DEMO STORE REFUND",
                "cost": -80.0,
                "category": "shopping",
                "source_debt": "CARDHOLDER_B",
            },
        ]
    return _shape_silver_frame(pd.DataFrame(rows))
