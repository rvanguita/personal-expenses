"""No-network tests for the Silver categorization matcher and the Gemini response reshaping."""

import json
import os
from contextlib import contextmanager

import pandas as pd

import src.expenses.ai_categorizer as cat
from src.expenses.ai_categorizer import (
    gemini_categorize_unmatched,
    match_merchants_with_history,
)

_CATEGORY_JSON = "data/categories.default.json"


def test_match_merchants_with_history_empty_and_missing_id():
    matched, unmatched = match_merchants_with_history(pd.DataFrame(), engine=None)
    assert list(matched.columns) == ["id", "category", "motivation", "categorized_by"]
    assert list(unmatched.columns) == ["id"]
    assert matched.empty and unmatched.empty

    matched, unmatched = match_merchants_with_history(pd.DataFrame({"cost": [1.0]}), engine=None)
    assert matched.empty and unmatched.empty


class _FakeEngine:
    @contextmanager
    def connect(self):
        yield object()


def test_history_match_takes_precedence_over_dictionary(monkeypatch):
    # "EXAMPLE ONLINE STORE" would resolve via the JSON keyword dictionary; a Silver history row
    # forces it to 'history_match' with the stored category instead.
    history = pd.DataFrame(
        [{"id": "EXAMPLE ONLINE STORE", "category": "Services", "motivation": "prior review"}]
    )
    monkeypatch.setattr(cat, "create_medallion_tables", lambda *a, **k: None)
    monkeypatch.setattr(cat.pd, "read_sql", lambda *a, **k: history)

    df_bronze = pd.DataFrame([{"id": "EXAMPLE ONLINE STORE"}, {"id": "TOTALLY UNKNOWN 42"}])
    matched, unmatched = match_merchants_with_history(df_bronze, engine=_FakeEngine())

    row = matched[matched["id"] == "EXAMPLE ONLINE STORE"].iloc[0]
    assert row["categorized_by"] == "history_match"
    assert row["category"] == "services"  # lower-cased from history
    assert "TOTALLY UNKNOWN 42" in unmatched["id"].values


def test_gemini_categorize_unmatched_reshapes_and_coerces(monkeypatch):
    class _Resp:
        text = json.dumps(
            [
                {"Estabelecimento": "PADARIA X", "Categoria": "food", "Motivo": "bakery"},
                {"Estabelecimento": "MISC Y", "Categoria": "bogus_category", "Motivo": "?"},
            ]
        )

    monkeypatch.setattr(cat, "gemini_category", lambda *a, **k: _Resp())
    mtime_before = os.path.getmtime(_CATEGORY_JSON)

    out = gemini_categorize_unmatched(pd.DataFrame([{"id": "PADARIA X"}, {"id": "MISC Y"}]))

    assert set(out.columns) >= {"id", "category", "motivation", "categorized_by"}
    assert (out["categorized_by"] == "gemini_ai").all()
    assert out.set_index("id").loc["PADARIA X", "category"] == "food"
    assert out.set_index("id").loc["MISC Y", "category"] == "not_found"  # unknown -> coerced
    # this function only reads the category dictionary, never writes it
    assert os.path.getmtime(_CATEGORY_JSON) == mtime_before


def test_gemini_categorize_unmatched_empty():
    out = gemini_categorize_unmatched(pd.DataFrame(columns=["id"]))
    assert out.empty
    assert list(out.columns) == ["id", "category", "motivation", "categorized_by"]
