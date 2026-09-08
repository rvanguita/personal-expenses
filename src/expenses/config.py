import json
import os
from pathlib import Path

import dotenv
import pandas as pd

# Load environment variables
dotenv.load_dotenv()

# Database environment variables
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))

# Unified Table Name across all Medallion database layers
MYSQL_TABLE = os.getenv("MYSQL_TABLE", os.getenv("MYSQL_ID_TABLE", "personal_expenses"))
MYSQL_ID_TABLE = MYSQL_TABLE

# Medallion Architecture Database Names
MYSQL_DB_RAW = os.getenv("MYSQL_DB_RAW", "raw")
MYSQL_DB_BRONZE = os.getenv("MYSQL_DB_BRONZE", "bronze")
MYSQL_DB_SILVER = os.getenv("MYSQL_DB_SILVER", "silver")

# Google Gemini API Key & Model
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# Category dictionary paths. The tracked seed is immutable; runtime learning is written to a
# git-ignored local file so merchant-derived data cannot be committed accidentally.
CATEGORY_SEED_PATH = Path("data/categories.default.json")
CATEGORY_LOCAL_PATH = Path(os.getenv("CATEGORY_LOCAL_PATH", "data/categories.local.json"))

# Streamlit Port Configuration
STREAMLIT_PORT = int(os.getenv("STREAMLIT_PORT", os.getenv("STREAMLIT_SERVER_PORT", "8503")))

# Category metadata, colors, and English labels
CATEGORY_CONFIG = {
    "food": {"label": "Food & Dining", "color": "#FF9800", "icon": "🍔"},
    "groceries": {"label": "Groceries", "color": "#4CAF50", "icon": "🛒"},
    "shopping": {"label": "Shopping", "color": "#2196F3", "icon": "🛍️"},
    "services": {"label": "Services & Subscriptions", "color": "#607D8B", "icon": "📱"},
    "transport": {"label": "Transportation", "color": "#00ACC1", "icon": "🚗"},
    "health": {"label": "Health & Pharmacy", "color": "#F44336", "icon": "💊"},
    "games": {"label": "Games & Leisure", "color": "#9C27B0", "icon": "🎮"},
    "home": {"label": "Home & Maintenance", "color": "#795548", "icon": "🏠"},
    "beauty": {"label": "Beauty & Personal Care", "color": "#E91E63", "icon": "💇"},
    "pet": {"label": "Pet Shop", "color": "#455A64", "icon": "🐾"},
    "travel": {"label": "Travel", "color": "#FFC107", "icon": "✈️"},
    "courses": {"label": "Courses", "color": "#DE07FF", "icon": "📚"},
    "education": {"label": "Education", "color": "#3F51B5", "icon": "🎓"},
    "not_found": {"label": "Uncategorized", "color": "#9E9E9E", "icon": "❓"},
}

CATEGORY_COLORS = {k: v["color"] for k, v in CATEGORY_CONFIG.items()}
CATEGORY_LABELS = {k: v["label"] for k, v in CATEGORY_CONFIG.items()}
LABEL_TO_CAT = {v["label"]: k for k, v in CATEGORY_CONFIG.items()}
CATEGORY_COLOR_MAP = {v["label"]: v["color"] for v in CATEGORY_CONFIG.values()}

DAY_OF_WEEK_LABELS_PT = {
    "Monday": "Segunda-feira",
    "Tuesday": "Terça-feira",
    "Wednesday": "Quarta-feira",
    "Thursday": "Quinta-feira",
    "Friday": "Sexta-feira",
    "Saturday": "Sábado",
    "Sunday": "Domingo",
}

# Analytics thresholds (single source of truth for both analytics.py defaults and the UI tabs)
REFERENCE_BUDGET_LIMIT = float(os.getenv("REFERENCE_BUDGET_LIMIT", "10000"))
ANOMALY_Z_THRESHOLD = 2.5
ANOMALY_MIN_CATEGORY_TX = 5
INSTALLMENT_BURDEN_WARNING_PCT = 40.0
RECURRING_MIN_MONTHS = 3
RECURRING_MAX_CV = 0.35

# Merchant name canonicalization — collapse noisy variants of one merchant into a single id so
# installment series (e.g. car insurance) aggregate as one merchant instead of scattering.
# Each value is a list of substrings matched case-insensitively against the upper-cased Silver
# `id`; the first canonical name whose pattern matches wins. Applied at read time in
# `database.load_expenses_data()` — Bronze/Silver stay untouched, so edits here take effect
# immediately with no re-ingest. Add merchants freely.
MERCHANT_ALIASES: dict[str, list[str]] = {
    "EXAMPLE MARKET": ["EXAMPLE MARKET", "EXAMPLE-MARKET", "EXAMPLE  MARKET"],
    "DEMO TRANSIT": ["DEMO TRANSIT", "DEMO-TRANSIT"],
}


def format_currency_br(val: float | None) -> str:
    """Formats numeric values to Brazilian Real currency string: R$ 1,234.56"""
    if val is None or pd.isna(val):
        return "R$ 0.00"
    is_neg = val < 0
    val_abs = abs(val)
    formatted = f"{val_abs:,.2f}"
    return f"-R$ {formatted}" if is_neg else f"R$ {formatted}"


def format_currency_md(val: float | None) -> str:
    """Formats numeric values safely for Streamlit markdown without triggering LaTeX math parsing ($ -> \\$)."""
    return format_currency_br(val).replace("$", "\\$")


def normalize_merchant_id(raw_id: str) -> str:
    """Maps a raw merchant id to its canonical name when it matches a `MERCHANT_ALIASES` pattern.

    Non-matching ids (and empty/None) are returned unchanged.
    """
    if not raw_id:
        return raw_id
    upper = str(raw_id).upper()
    for canonical, patterns in MERCHANT_ALIASES.items():
        if any(pattern.upper() in upper for pattern in patterns):
            return canonical
    return raw_id


def get_category_color(cat: str) -> str:
    return CATEGORY_CONFIG.get(cat, {}).get("color", "#9E9E9E")


def get_category_label(cat: str) -> str:
    return CATEGORY_CONFIG.get(cat, {}).get("label", cat)


def read_file(path: str | Path, is_json: bool = False):
    with open(path, encoding="utf-8") as f:
        if is_json:
            return json.load(f)
        return f.read()


def load_category_dictionary() -> dict[str, list[str]]:
    """Load the generic seed and merge optional, machine-local learned terms into it."""
    try:
        seed = read_file(CATEGORY_SEED_PATH, is_json=True)
    except (OSError, json.JSONDecodeError):
        seed = {}

    try:
        local = read_file(CATEGORY_LOCAL_PATH, is_json=True)
    except (OSError, json.JSONDecodeError):
        local = {}

    merged: dict[str, list[str]] = {}
    for source in (seed, local):
        for category, terms in source.items():
            if not isinstance(terms, list):
                continue
            merged.setdefault(category, [])
            for term in terms:
                if isinstance(term, str) and term and term not in merged[category]:
                    merged[category].append(term)
    return merged


def save_local_category_dictionary(categories: dict[str, list[str]]) -> None:
    """Persist the effective dictionary only to the ignored machine-local data file."""
    CATEGORY_LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CATEGORY_LOCAL_PATH, "w", encoding="utf-8") as file:
        json.dump(categories, file, ensure_ascii=False, indent=2)
        file.write("\n")
