"""pt-BR formatting used by the Dash app."""

import math

from app.dash.fmt import (
    CATEGORY_LABELS_PT,
    LABEL_PT_TO_KEY,
    brl,
    integer,
    pct,
)
from src.expenses.config import CATEGORY_CONFIG


def test_brl():
    assert brl(1234.5) == "R$ 1.234,50"
    assert brl(1234567.891) == "R$ 1.234.567,89"
    assert brl(-80) == "-R$ 80,00"
    assert brl(0) == "R$ 0,00"
    assert brl(-0.001) == "R$ 0,00"
    assert brl(None) == "R$ 0,00"
    assert brl(math.nan) == "R$ 0,00"
    assert brl(4175.2, 0) == "R$ 4.175"


def test_pct_and_integer():
    assert pct(12.345) == "12,3%"
    assert pct(12.345, signed=True) == "+12,3%"
    assert pct(-8, signed=True) == "-8,0%"
    assert pct(0, signed=True) == "0,0%"
    assert integer(1234) == "1.234"


def test_every_category_has_a_unique_portuguese_label():
    assert set(CATEGORY_CONFIG) <= set(CATEGORY_LABELS_PT)
    assert len(LABEL_PT_TO_KEY) == len(CATEGORY_LABELS_PT)
