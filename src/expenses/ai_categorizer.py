import json
import re
from pathlib import Path

import pandas as pd
import sqlalchemy

from src.expenses.config import (
    CATEGORY_CONFIG,
    MYSQL_DB_BRONZE,
    MYSQL_DB_RAW,
    MYSQL_DB_SILVER,
    MYSQL_TABLE,
    load_category_dictionary,
    read_file,
    save_local_category_dictionary,
)
from src.expenses.database import (
    create_medallion_tables,
    get_db_engine,
    load_bronze_data,
    save_dataframe_replace,
)
from src.expenses.runtime import clear_caches, notify_error, notify_warning
from src.gemini import gemini_category


def match_merchants_with_history(
    df_bronze: pd.DataFrame, engine=None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compares distinct merchants in df_bronze against Silver history and category dictionary.

    Returns:
        tuple[df_matched, df_unmatched]:
        - df_matched: merchants with known category (id, category, motivation, categorized_by='history_match')
        - df_unmatched: deduplicated unknown merchants (id) needing Gemini categorization
    """
    if df_bronze.empty or "id" not in df_bronze.columns:
        return pd.DataFrame(
            columns=["id", "category", "motivation", "categorized_by"]
        ), pd.DataFrame(columns=["id"])

    unique_merchants = df_bronze[["id"]].drop_duplicates().copy()

    # 1. Fetch known categorized merchants from Silver database in MySQL
    history_map = {}
    engine_silver = engine if engine is not None else get_db_engine(MYSQL_DB_SILVER)
    if engine_silver is not None:
        try:
            create_medallion_tables()
            with engine_silver.connect() as conn:
                existing_silver = pd.read_sql(
                    sqlalchemy.text(
                        f"SELECT DISTINCT id, category, motivation FROM {MYSQL_TABLE} WHERE category != 'not_found'"
                    ),
                    conn,
                )
                if not existing_silver.empty:
                    for _, row in existing_silver.iterrows():
                        m_id = str(row["id"]).strip().upper()
                        history_map[m_id] = {
                            "category": str(row["category"]).strip().lower(),
                            "motivation": str(row.get("motivation", "Historical match")),
                            "categorized_by": "history_match",
                        }
        except Exception:  # noqa: BLE001
            pass

    # 2. Check JSON category dictionary for term matching
    dict_categories = load_category_dictionary()

    matched_rows = []
    unmatched_rows = []

    for _, row in unique_merchants.iterrows():
        merchant_name = str(row["id"]).strip().upper()

        if merchant_name in history_map:
            matched_rows.append(
                {
                    "id": merchant_name,
                    "category": history_map[merchant_name]["category"],
                    "motivation": history_map[merchant_name]["motivation"],
                    "categorized_by": "history_match",
                }
            )
            continue

        # Check if merchant name contains any keyword from dictionary
        found_in_dict = False
        for cat, keywords in dict_categories.items():
            if isinstance(keywords, list):
                for kw in keywords:
                    if kw.upper() in merchant_name:
                        matched_rows.append(
                            {
                                "id": merchant_name,
                                "category": cat,
                                "motivation": f"Keyword '{kw}' matched in dictionary",
                                "categorized_by": "dictionary_match",
                            }
                        )
                        found_in_dict = True
                        break
            if found_in_dict:
                break

        if not found_in_dict:
            unmatched_rows.append({"id": merchant_name})

    df_matched = pd.DataFrame(matched_rows)
    df_unmatched = pd.DataFrame(unmatched_rows)

    if df_matched.empty:
        df_matched = pd.DataFrame(columns=["id", "category", "motivation", "categorized_by"])
    if df_unmatched.empty:
        df_unmatched = pd.DataFrame(columns=["id"])

    return df_matched, df_unmatched


def gemini_categorize_unmatched(df_unmatched: pd.DataFrame) -> pd.DataFrame:
    """Invokes Gemini AI for a single batch of unique unknown merchants with safe fallback."""
    if df_unmatched.empty or "id" not in df_unmatched.columns:
        return pd.DataFrame(columns=["id", "category", "motivation", "categorized_by"])

    path_prompt = Path("template/prompt.md")
    categories = load_category_dictionary()

    try:
        prompt_template = read_file(path_prompt)
        prompt = prompt_template.format(
            category=json.dumps(categories, ensure_ascii=False, indent=2)
        )
    except Exception as e:  # noqa: BLE001
        notify_error(f"Error reading prompt template: {e}")
        prompt = f"Categorize the merchants using the following categories: {list(CATEGORY_CONFIG.keys())}"

    unique_ids = df_unmatched[["id"]].drop_duplicates().to_dict(orient="records")

    try:
        response = gemini_category(prompt=prompt, data=unique_ids)
        resp_text = response.text.strip()
        if resp_text.startswith("```"):
            resp_text = re.sub(r"^```(?:json)?\n", "", resp_text)
            resp_text = re.sub(r"\n```$", "", resp_text)

        parsed_json = json.loads(resp_text)
        df_resp = pd.DataFrame(parsed_json)
        df_resp = df_resp.rename(
            columns={
                "Estabelecimento": "id",
                "Categoria": "category",
                "Motivo": "motivation",
            }
        )
        if "category" not in df_resp.columns:
            df_resp["category"] = "not_found"
        if "motivation" not in df_resp.columns:
            df_resp["motivation"] = "not_found"

        df_resp["category"] = df_resp["category"].astype(str).str.strip().str.lower()
        df_resp["category"] = df_resp["category"].apply(
            lambda c: c if c in CATEGORY_CONFIG else "not_found"
        )
        df_resp["categorized_by"] = "gemini_ai"
        return df_resp
    except Exception as e:  # noqa: BLE001
        notify_warning(f"⚠️ Gemini classification notice for current batch: {e}")
        return pd.DataFrame(
            [
                {
                    "id": row["id"],
                    "category": "not_found",
                    "motivation": "Temporarily unclassified / Manual review",
                    "categorized_by": "gemini_ai",
                }
                for row in unique_ids
            ]
        )


def batch_gemini_categorize_unmatched(
    df_unmatched: pd.DataFrame, batch_size: int = 25, progress_callback=None
) -> pd.DataFrame:
    """Splits unique unknown merchant IDs into chunks of `batch_size` (default 25) and categorizes via Gemini AI."""
    if df_unmatched.empty or "id" not in df_unmatched.columns:
        return pd.DataFrame(columns=["id", "category", "motivation", "categorized_by"])

    unique_merchants = df_unmatched[["id"]].drop_duplicates().reset_index(drop=True)
    total_count = len(unique_merchants)
    num_batches = (total_count + batch_size - 1) // batch_size
    batch_results = []

    for i in range(0, total_count, batch_size):
        batch_num = (i // batch_size) + 1
        chunk = unique_merchants.iloc[i : i + batch_size]
        if progress_callback:
            progress_callback(batch_num, num_batches, len(chunk), total_count)

        res_chunk = gemini_categorize_unmatched(chunk)
        batch_results.append(res_chunk)

    if batch_results:
        return pd.concat(batch_results, ignore_index=True)
    return pd.DataFrame(columns=["id", "category", "motivation", "categorized_by"])


def gemini_categorize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Legacy helper maintained for backward compatibility."""
    return gemini_categorize_unmatched(df)


def save_medallion_pipeline(
    df_raw: pd.DataFrame,
    df_bronze: pd.DataFrame,
    df_silver_reviewed: pd.DataFrame,
    engine=None,
) -> dict:
    """Sequentially persists records into RAW, BRONZE, and SILVER database layers with deduplication."""
    create_medallion_tables()
    engine_raw = get_db_engine(MYSQL_DB_RAW)
    engine_bronze = get_db_engine(MYSQL_DB_BRONZE)
    engine_silver = get_db_engine(MYSQL_DB_SILVER)

    # 1. Update Category Dictionary with newly confirmed categories/motivations
    categories = load_category_dictionary()

    if "motivation" in df_silver_reviewed.columns and "category" in df_silver_reviewed.columns:
        new_categories = (
            df_silver_reviewed.groupby("category")["motivation"]
            .apply(lambda x: x.dropna().drop_duplicates().tolist())
            .to_dict()
        )
        for category, motivations in new_categories.items():
            categories.setdefault(category, [])
            for motivation in motivations:
                if (
                    motivation
                    and motivation != "not_found"
                    and motivation not in categories[category]
                ):
                    categories[category].append(motivation)

        save_local_category_dictionary(categories)

    # 2. Persist RAW Layer (Exact copy as input into raw database)
    raw_inserted = 0
    if not df_raw.empty and engine_raw is not None:
        try:
            df_raw.to_sql(MYSQL_TABLE, con=engine_raw, if_exists="append", index=False)
            raw_inserted = len(df_raw)
        except Exception as e:  # noqa: BLE001
            notify_error(f"Error saving to Raw database: {e}")

    # 3. Persist BRONZE Layer (Cleaned & Standardized into bronze database)
    bronze_inserted = 0
    bronze_duplicates = 0
    if not df_bronze.empty and engine_bronze is not None:
        try:
            with engine_bronze.connect() as conn:
                existing_bronze = pd.read_sql(
                    sqlalchemy.text(
                        f"SELECT date, date_buy, id, cost, installment FROM {MYSQL_TABLE}"
                    ),
                    conn,
                )
            if not existing_bronze.empty:
                existing_bronze["key"] = (
                    existing_bronze["date"].astype(str)
                    + "_"
                    + existing_bronze["date_buy"].astype(str)
                    + "_"
                    + existing_bronze["id"].astype(str)
                    + "_"
                    + existing_bronze["cost"].astype(str)
                    + "_"
                    + existing_bronze["installment"].astype(str)
                )
                df_bronze_check = df_bronze.copy()
                df_bronze_check["key"] = (
                    df_bronze_check["date"].astype(str)
                    + "_"
                    + df_bronze_check["date_buy"].astype(str)
                    + "_"
                    + df_bronze_check["id"].astype(str)
                    + "_"
                    + df_bronze_check["cost"].astype(str)
                    + "_"
                    + df_bronze_check["installment"].astype(str)
                )
                new_bronze = df_bronze_check[
                    ~df_bronze_check["key"].isin(existing_bronze["key"])
                ].drop(columns=["key"], errors="ignore")
            else:
                new_bronze = df_bronze

            bronze_inserted = len(new_bronze)
            bronze_duplicates = len(df_bronze) - bronze_inserted
            if bronze_inserted > 0:
                new_bronze.to_sql(MYSQL_TABLE, con=engine_bronze, if_exists="append", index=False)
        except Exception as e:  # noqa: BLE001
            notify_error(f"Error saving to Bronze database: {e}")

    # 4. Persist SILVER Layer (Enriched & Categorized into silver database)
    silver_inserted = 0
    silver_duplicates = 0
    if not df_silver_reviewed.empty and engine_silver is not None:
        try:
            with engine_silver.connect() as conn:
                existing_silver = pd.read_sql(
                    sqlalchemy.text(
                        f"SELECT date, date_buy, id, cost, installment FROM {MYSQL_TABLE}"
                    ),
                    conn,
                )
            if not existing_silver.empty:
                existing_silver["key"] = (
                    existing_silver["date"].astype(str)
                    + "_"
                    + existing_silver["date_buy"].astype(str)
                    + "_"
                    + existing_silver["id"].astype(str)
                    + "_"
                    + existing_silver["cost"].astype(str)
                    + "_"
                    + existing_silver["installment"].astype(str)
                )
                df_silver_check = df_silver_reviewed.copy()
                df_silver_check["key"] = (
                    df_silver_check["date"].astype(str)
                    + "_"
                    + df_silver_check["date_buy"].astype(str)
                    + "_"
                    + df_silver_check["id"].astype(str)
                    + "_"
                    + df_silver_check["cost"].astype(str)
                    + "_"
                    + df_silver_check["installment"].astype(str)
                )
                new_silver = df_silver_check[
                    ~df_silver_check["key"].isin(existing_silver["key"])
                ].drop(columns=["key"], errors="ignore")
            else:
                new_silver = df_silver_reviewed

            silver_inserted = len(new_silver)
            silver_duplicates = len(df_silver_reviewed) - silver_inserted
            if silver_inserted > 0:
                new_silver.to_sql(MYSQL_TABLE, con=engine_silver, if_exists="append", index=False)
                clear_caches()
        except Exception as e:  # noqa: BLE001
            notify_error(f"Error saving to Silver database: {e}")

    return {
        "raw_inserted": raw_inserted,
        "bronze_inserted": bronze_inserted,
        "bronze_duplicates": bronze_duplicates,
        "silver_inserted": silver_inserted,
        "silver_duplicates": silver_duplicates,
    }


def repopulate_silver_layer(batch_size: int = 25, progress_callback=None) -> dict:
    """Repopulates the Silver database from Bronze data with auto-matching and incremental batch saving.

    1. Loads all records from Bronze database layer.
    2. Matches known merchants against Silver history and category dictionary.
    3. Iteratively processes unknown merchants in chunks of `batch_size` (default 25 IDs).
    4. Progressively saves to MySQL Silver database and updates the dictionary after EACH batch.
    """
    create_medallion_tables()
    engine_silver = get_db_engine(MYSQL_DB_SILVER)
    df_bronze = load_bronze_data()

    if df_bronze.empty:
        return {
            "status": "empty",
            "total_bronze": 0,
            "matched_count": 0,
            "ai_count": 0,
            "silver_count": 0,
        }

    # Step 1: Match with Silver history and dictionary
    df_matched, df_unmatched = match_merchants_with_history(df_bronze, engine_silver)

    def _sync_to_silver(df_current_map: pd.DataFrame) -> pd.DataFrame:
        """Helper to build and persist the current accumulated dataset into the Silver database layer."""
        df_silver_build = pd.merge(
            df_bronze,
            df_current_map[["id", "category", "motivation", "categorized_by"]].drop_duplicates(
                subset=["id"]
            ),
            on="id",
            how="left",
        )
        df_silver_build["category"] = df_silver_build["category"].fillna("not_found")
        df_silver_build["motivation"] = df_silver_build["motivation"].fillna("Manual review")
        df_silver_build["categorized_by"] = df_silver_build["categorized_by"].fillna("pending")

        if engine_silver is not None:
            save_dataframe_replace(df_silver_build, engine_silver, MYSQL_DB_SILVER)
            clear_caches()
        # Update JSON dictionary
        categories = load_category_dictionary()

        new_categories = (
            df_silver_build.groupby("category")["motivation"]
            .apply(lambda x: x.dropna().drop_duplicates().tolist())
            .to_dict()
        )
        for category, motivations in new_categories.items():
            categories.setdefault(category, [])
            for motivation in motivations:
                if (
                    motivation
                    and motivation != "not_found"
                    and motivation not in categories[category]
                ):
                    categories[category].append(motivation)

        save_local_category_dictionary(categories)

        return df_silver_build

    # Initial progressive save of all matched items
    accumulated_categories = (
        df_matched.copy()
        if not df_matched.empty
        else pd.DataFrame(columns=["id", "category", "motivation", "categorized_by"])
    )
    df_silver_latest = _sync_to_silver(accumulated_categories)

    # Step 2: Batch Gemini AI for unmatched unique merchants with progressive saving
    if not df_unmatched.empty:
        unique_merchants = df_unmatched[["id"]].drop_duplicates().reset_index(drop=True)
        total_count = len(unique_merchants)
        num_batches = (total_count + batch_size - 1) // batch_size

        for i in range(0, total_count, batch_size):
            batch_num = (i // batch_size) + 1
            chunk = unique_merchants.iloc[i : i + batch_size]

            if progress_callback:
                progress_callback(batch_num, num_batches, len(chunk), total_count, "calling")

            res_chunk = gemini_categorize_unmatched(chunk)
            accumulated_categories = pd.concat(
                [accumulated_categories, res_chunk], ignore_index=True
            )

            # Progressive persistence: Save this batch immediately to the Silver layer
            df_silver_latest = _sync_to_silver(accumulated_categories)

            if progress_callback:
                progress_callback(batch_num, num_batches, len(chunk), total_count, "saved")

    return {
        "status": "success",
        "total_bronze": len(df_bronze),
        "matched_count": len(df_matched),
        "ai_count": len(df_unmatched),
        "silver_count": len(df_silver_latest),
        "df_silver": df_silver_latest,
    }


def save_categorized_expenses(
    df_raw: pd.DataFrame, df_resp: pd.DataFrame, engine=None
) -> tuple[int, int]:
    """Legacy helper maintained for backward compatibility."""
    df_bronze = df_raw.copy() if "date" in df_raw.columns else df_raw
    df_silver_reviewed = pd.merge(
        df_bronze, df_resp[["id", "category", "motivation"]], on="id", how="left"
    )
    df_silver_reviewed["category"] = df_silver_reviewed["category"].fillna("not_found")
    df_silver_reviewed["categorized_by"] = "legacy"
    res = save_medallion_pipeline(pd.DataFrame(), df_bronze, df_silver_reviewed, engine)
    return res["silver_inserted"], res["silver_duplicates"]
