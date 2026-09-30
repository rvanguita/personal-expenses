"""pt-BR formatting used by the Dash app."""

import math

from expenses.config import CATEGORY_CONFIG
from expenses_dash.fmt import (
    CATEGORY_LABELS,
    LABEL_TO_KEY,
    _number,
    brl,
    integer,
    pct,
)


def test_brl():
    assert brl(1234.5) == "R$ 1,234.50"
    assert brl(1234567.891) == "R$ 1,234,567.89"
    assert brl(-80) == "-R$ 80.00"
    assert brl(0) == "R$ 0.00"
    assert brl(-0.001) == "R$ 0.00"
    assert brl(None) == "R$ 0.00"
    assert brl(math.nan) == "R$ 0.00"
    assert brl(4175.2, 0) == "R$ 4,175"


def test_pct_and_integer():
    assert pct(12.345) == "12.3%"
    assert pct(12.345, signed=True) == "+12.3%"
    assert pct(-8, signed=True) == "-8.0%"
    assert pct(0, signed=True) == "0.0%"
    assert integer(1234) == "1,234"


def test_every_category_has_a_unique_portuguese_label():
    assert set(CATEGORY_CONFIG) <= set(CATEGORY_LABELS)
    assert len(LABEL_TO_KEY) == len(CATEGORY_LABELS)


def test_number_separators():
    assert _number(1234567.891, 2) == "1,234,567.89"
    assert _number(-5, 0) == "5"  # sign is added by the callers
