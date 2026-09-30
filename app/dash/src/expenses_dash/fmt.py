"""Presentation helpers for the Dash app: currency, percentages, counts and display names.

Amounts are Brazilian reais shown with English separators (``R$ 1,234.56``), the same format as
``config.format_currency_br`` in the Streamlit app. Category names come from ``config``.
"""

import math

from expenses.config import CATEGORY_LABELS, LABEL_TO_CAT

LABEL_TO_KEY = LABEL_TO_CAT
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def category_label(key: str) -> str:
    return CATEGORY_LABELS.get(key, key)


def _number(value: float, decimals: int) -> str:
    """1234.5 -> '1,234.50' (absolute value; callers add the sign)."""
    return f"{abs(value):,.{decimals}f}"


def brl(value: float | None, decimals: int = 2) -> str:
    """1234.5 -> 'R$ 1,234.50'; negatives -> '-R$ 1,234.50'; None/NaN -> 'R$ 0.00'."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        value = 0.0
    sign = "-" if value < 0 and round(abs(value), decimals) > 0 else ""
    return f"{sign}R$ {_number(value, decimals)}"


def pct(value: float, decimals: int = 1, signed: bool = False) -> str:
    """12.345 -> '12.3%' (or '+12.3%' with ``signed``)."""
    sign = (
        ("+" if value > 0 else "-" if value < 0 else "") if signed else ("-" if value < 0 else "")
    )
    return f"{sign}{_number(value, decimals)}%"


def integer(value: float) -> str:
    """1234 -> '1,234'."""
    return _number(value, 0)
