import json

import src.expenses.config as config
from src.expenses.config import (
    CATEGORY_COLOR_MAP,
    CATEGORY_COLORS,
    CATEGORY_CONFIG,
    CATEGORY_LABELS,
    LABEL_TO_CAT,
    MERCHANT_ALIASES,
    format_currency_br,
    format_currency_md,
    get_category_color,
    get_category_label,
    load_category_dictionary,
    normalize_merchant_id,
    read_file,
    save_local_category_dictionary,
)


def test_format_currency_br():
    assert format_currency_br(1234.56) == "R$ 1,234.56"
    assert format_currency_br(-50.0) == "-R$ 50.00"
    assert format_currency_br(0) == "R$ 0.00"
    assert format_currency_br(None) == "R$ 0.00"
    assert format_currency_br(float("nan")) == "R$ 0.00"


def test_format_currency_md():
    assert format_currency_md(1234.56) == "R\\$ 1,234.56"
    assert format_currency_md(-50.0) == "-R\\$ 50.00"


def test_category_config_integrity():
    for cat, meta in CATEGORY_CONFIG.items():
        assert "label" in meta
        assert "color" in meta
        assert "icon" in meta
        assert cat in CATEGORY_LABELS


def test_category_helpers():
    assert get_category_color("food") == "#FF9800"
    assert get_category_color("non_existent") == "#9E9E9E"
    assert get_category_label("shopping") == "Shopping"
    assert get_category_label("custom_cat") == "custom_cat"


def test_normalize_merchant_id_collapses_variants():
    assert normalize_merchant_id("EXAMPLE-MARKET SERVICE") == "EXAMPLE MARKET"
    assert normalize_merchant_id("EXAMPLE  MARKET ONLINE") == "EXAMPLE MARKET"
    assert normalize_merchant_id("DEMO-TRANSIT RIDE") == "DEMO TRANSIT"


def test_normalize_merchant_id_passthrough():
    assert normalize_merchant_id("UNLISTED STORE") == "UNLISTED STORE"
    assert normalize_merchant_id("") == ""
    assert normalize_merchant_id(None) is None


def test_merchant_aliases_shape():
    for canonical, patterns in MERCHANT_ALIASES.items():
        assert isinstance(canonical, str) and canonical
        assert isinstance(patterns, list) and patterns
        assert all(isinstance(p, str) and p for p in patterns)


def test_category_derived_maps_parity():
    keys = set(CATEGORY_CONFIG)
    assert set(CATEGORY_COLORS) == keys
    assert set(CATEGORY_LABELS) == keys
    assert "not_found" in CATEGORY_CONFIG
    # label -> key inverse round-trips for every category
    for key, meta in CATEGORY_CONFIG.items():
        assert LABEL_TO_CAT[meta["label"]] == key
        assert CATEGORY_COLOR_MAP[meta["label"]] == meta["color"]


def test_read_file_text_and_json():
    text = read_file("template/prompt.md")
    assert isinstance(text, str) and text.strip()

    data = read_file("data/categories.default.json", is_json=True)
    assert isinstance(data, dict)
    assert all(isinstance(v, list) for v in data.values())


def test_category_dictionary_merges_seed_and_local_without_mutating_seed(tmp_path, monkeypatch):
    seed_path = tmp_path / "categories.default.json"
    local_path = tmp_path / "categories.local.json"
    seed_path.write_text(json.dumps({"food": ["Bakery"]}), encoding="utf-8")
    local_path.write_text(json.dumps({"food": ["Cafe"], "travel": ["Hotel"]}), encoding="utf-8")
    seed_before = seed_path.read_text(encoding="utf-8")
    monkeypatch.setattr(config, "CATEGORY_SEED_PATH", seed_path)
    monkeypatch.setattr(config, "CATEGORY_LOCAL_PATH", local_path)

    assert load_category_dictionary() == {"food": ["Bakery", "Cafe"], "travel": ["Hotel"]}
    save_local_category_dictionary({"food": ["Bakery", "Cafe", "Restaurant"]})

    assert seed_path.read_text(encoding="utf-8") == seed_before
    assert json.loads(local_path.read_text(encoding="utf-8")) == {
        "food": ["Bakery", "Cafe", "Restaurant"]
    }
