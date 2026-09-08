"""Framework-agnostic sidebar-filter logic for the Streamlit frontend.

`apply_filters` is the single source of truth for turning the full Silver frame plus a filter
dict (as produced by the sidebar) into the `df_filtered` every tab renders.
"""

import pandas as pd

# Transaction-type filter options (exact strings both sidebars must emit).
TX_NET = "Net Expenses (Purchases - Refunds)"
TX_GROSS = "Gross Purchases Only (Positive)"
TX_REFUNDS = "Refunds Only (Negative)"
TX_ALL = "All Transactions"
TX_TYPE_OPTIONS = [TX_NET, TX_GROSS, TX_REFUNDS, TX_ALL]

# Payment-method filter options.
INSTALLMENT_ALL = "All"
INSTALLMENT_SINGLE = "Single Payment Only"
INSTALLMENT_ONLY = "Installments Only"
INSTALLMENT_OPTIONS = [INSTALLMENT_ALL, INSTALLMENT_SINGLE, INSTALLMENT_ONLY]

# Predefined-period options and how many trailing months each keeps.
PERIOD_OPTIONS = ["Last 6 months", "Last 3 months", "Last 12 months", "All History", "Custom"]
PERIOD_MONTHS = {
    "Last 3 months": 3,
    "Last 6 months": 6,
    "Last 12 months": 12,
}

# Empty-state defaults — mirrors the fallback dict returned by the Streamlit sidebar.
DEFAULT_FILTERS: dict = {
    "selected_months": [],
    "selected_holders": [],
    "selected_categories": [],
    "tx_type": TX_NET,
    "installment_type": INSTALLMENT_ALL,
    "search_id": "",
}


def apply_filters(df_full: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Slices the full Silver frame down to the user's active sidebar selection.

    Args:
        df_full: the enriched frame from ``database.load_expenses_data`` (carries the derived
            ``year_month`` / ``is_payment`` / ``is_refund`` / ``is_installment`` columns).
        filters: dict with any of the keys in ``DEFAULT_FILTERS``. Missing or empty values mean
            "no filter for this dimension". ``selected_categories`` holds category *keys*
            (frontends map display labels to keys before calling).

    Returns:
        A filtered copy of ``df_full`` (never a view; ``df_full`` is not mutated). An empty
        input frame yields an empty frame.
    """
    if df_full.empty:
        return pd.DataFrame()

    df_filtered = df_full.copy()

    if filters.get("selected_months"):
        df_filtered = df_filtered[df_filtered["year_month"].isin(filters["selected_months"])]

    if filters.get("selected_holders"):
        df_filtered = df_filtered[df_filtered["source_debt"].isin(filters["selected_holders"])]

    if filters.get("selected_categories"):
        df_filtered = df_filtered[df_filtered["category"].isin(filters["selected_categories"])]

    # Transaction type filtering
    tx_filter = filters.get("tx_type", TX_NET)
    if tx_filter == TX_NET:
        df_filtered = df_filtered[~df_filtered["is_payment"]]
    elif tx_filter == TX_GROSS:
        df_filtered = df_filtered[(~df_filtered["is_payment"]) & (df_filtered["cost"] > 0)]
    elif tx_filter == TX_REFUNDS:
        df_filtered = df_filtered[df_filtered["is_refund"]]
    # TX_ALL retains all rows including payment settlements

    if filters.get("installment_type") == INSTALLMENT_SINGLE:
        df_filtered = df_filtered[~df_filtered["is_installment"]]
    elif filters.get("installment_type") == INSTALLMENT_ONLY:
        df_filtered = df_filtered[df_filtered["is_installment"]]

    if filters.get("search_id", "").strip():
        df_filtered = df_filtered[
            df_filtered["id"].str.contains(filters["search_id"].strip(), case=False, na=False)
        ]

    return df_filtered


def resolve_default_months(period_option: str, all_year_months: list[str]) -> list[str]:
    """Maps a predefined-period choice to the trailing ``year_month`` slice.

    ``all_year_months`` must be sorted newest-first. "All History" returns everything; "Custom"
    (and anything unrecognised) falls back to the last 6 months, matching the sidebar.
    """
    if period_option == "All History":
        return list(all_year_months)
    count = PERIOD_MONTHS.get(period_option, 6)
    return all_year_months[:count]
