"""pt-BR presentation helpers for the Dash app: currency, percentages and category names.

`config.format_currency_br` keeps its historical ``R$ 1,234.56`` output for the Streamlit app;
the Dash app formats the Brazilian way (``R$ 1.234,56``) and names categories in Portuguese.
"""

import math

from expenses.config import CATEGORY_CONFIG

CATEGORY_LABELS_PT = {
    "food": "Alimentação",
    "groceries": "Mercado",
    "shopping": "Compras",
    "services": "Serviços e assinaturas",
    "transport": "Transporte",
    "health": "Saúde e farmácia",
    "games": "Jogos e lazer",
    "home": "Casa e manutenção",
    "beauty": "Beleza e cuidados",
    "pet": "Pet",
    "travel": "Viagem",
    "courses": "Cursos",
    "education": "Educação",
    "not_found": "Sem categoria",
}
# Any category added to config later still gets a name (its English label) until translated.
for _key, _meta in CATEGORY_CONFIG.items():
    CATEGORY_LABELS_PT.setdefault(_key, _meta["label"])
LABEL_PT_TO_KEY = {label: key for key, label in CATEGORY_LABELS_PT.items()}

WEEKDAYS_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def category_label(key: str) -> str:
    return CATEGORY_LABELS_PT.get(key, key)


def _number(value: float, decimals: int) -> str:
    """1234.5 -> '1.234,50' (pt-BR separators)."""
    text = f"{abs(value):,.{decimals}f}"
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def brl(value: float | None, decimals: int = 2) -> str:
    """1234.5 -> 'R$ 1.234,50'; negatives -> '-R$ 1.234,50'; None/NaN -> 'R$ 0,00'."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        value = 0.0
    sign = "-" if value < 0 and round(abs(value), decimals) > 0 else ""
    return f"{sign}R$ {_number(value, decimals)}"


def pct(value: float, decimals: int = 1, signed: bool = False) -> str:
    """12.345 -> '12,3%' (or '+12,3%' with ``signed``)."""
    sign = (
        ("+" if value > 0 else "-" if value < 0 else "") if signed else ("-" if value < 0 else "")
    )
    return f"{sign}{_number(value, decimals)}%"


def integer(value: float) -> str:
    """1234 -> '1.234'."""
    return _number(value, 0)
