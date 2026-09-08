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
