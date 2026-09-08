import pandas as pd
import sqlalchemy

from src.expenses.config import (
    CATEGORY_CONFIG,
    CATEGORY_LABELS,
    MYSQL_DB_BRONZE,
    MYSQL_DB_RAW,
    MYSQL_DB_SILVER,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    MYSQL_TABLE,
    MYSQL_USER,
    normalize_merchant_id,
)
from src.expenses.runtime import cache_data, cache_resource, clear_caches, notify_error


def ensure_databases_exist() -> None:
    """Ensures that the raw, bronze, and silver databases exist on the MySQL server."""
    if not all([MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_PORT]):
        return
    try:
        url_server = sqlalchemy.engine.URL.create(
            drivername="mysql+pymysql",
            username=MYSQL_USER,
            password=MYSQL_PASSWORD,
            host=MYSQL_HOST,
            port=MYSQL_PORT,
        )
        engine_server = sqlalchemy.create_engine(url_server)
        with engine_server.connect() as conn:
            conn.execute(sqlalchemy.text(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DB_RAW};"))
            conn.execute(sqlalchemy.text(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DB_BRONZE};"))
            conn.execute(sqlalchemy.text(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DB_SILVER};"))
            conn.commit()
    except Exception:  # noqa: BLE001
        pass


@cache_resource
def get_db_engine(database: str = MYSQL_DB_SILVER):
    """Initializes and caches the SQLAlchemy database engine for a specific medallion database layer."""
    if not all([MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_PORT]):
        return None
    url = sqlalchemy.engine.URL.create(
        drivername="mysql+pymysql",
        username=MYSQL_USER,
        password=MYSQL_PASSWORD,
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        database=database,
    )
    return sqlalchemy.create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


def align_table_columns(engine, expected_columns: dict[str, str]) -> None:
    """Ensures that all expected columns exist in MYSQL_TABLE, dynamically altering the schema if missing."""
    if engine is None:
        return
    try:
        with engine.connect() as conn:
            cols_res = conn.execute(sqlalchemy.text(f"DESCRIBE {MYSQL_TABLE};"))
            existing_cols = {r[0].lower() for r in cols_res.fetchall()}
            for col_name, col_type in expected_columns.items():
                if col_name.lower() not in existing_cols:
                    conn.execute(
                        sqlalchemy.text(
                            f"ALTER TABLE {MYSQL_TABLE} ADD COLUMN {col_name} {col_type};"
                        )
                    )
            conn.commit()
    except Exception:  # noqa: BLE001
        pass


def create_medallion_tables(engine=None) -> None:
    """Ensures that the unified MYSQL_TABLE exists in each of the Raw, Bronze, and Silver databases."""
    ensure_databases_exist()

    # 1. RAW Layer: exact input data as received in CSV
    engine_raw = get_db_engine(MYSQL_DB_RAW)
    if engine_raw is not None:
        try:
            with engine_raw.connect() as conn:
                conn.execute(
                    sqlalchemy.text(
                        f"""
                        CREATE TABLE IF NOT EXISTS {MYSQL_TABLE} (
                            raw_date VARCHAR(50) NULL,
                            raw_id VARCHAR(255) NULL,
                            raw_portador VARCHAR(100) NULL,
                            raw_cost VARCHAR(50) NULL,
                            raw_installment VARCHAR(50) NULL,
                            data VARCHAR(50) NULL,
                            estabelecimento VARCHAR(255) NULL,
                            portador VARCHAR(100) NULL,
                            valor VARCHAR(50) NULL,
                            parcela VARCHAR(50) NULL,
                            invoice_date DATE NULL,
                            source_file VARCHAR(255) NULL,
                            created_at DATETIME NULL
                        );
                        """
                    )
                )
                conn.commit()
        except Exception:  # noqa: BLE001
            pass

        align_table_columns(
            engine_raw,
            {
                "data": "VARCHAR(50) NULL",
                "estabelecimento": "VARCHAR(255) NULL",
                "portador": "VARCHAR(100) NULL",
                "valor": "VARCHAR(50) NULL",
                "parcela": "VARCHAR(50) NULL",
                "raw_date": "VARCHAR(50) NULL",
                "raw_id": "VARCHAR(255) NULL",
                "raw_portador": "VARCHAR(100) NULL",
                "raw_cost": "VARCHAR(50) NULL",
                "raw_installment": "VARCHAR(50) NULL",
                "invoice_date": "DATE NULL",
                "source_file": "VARCHAR(255) NULL",
                "created_at": "DATETIME NULL",
            },
        )

    # 2. BRONZE Layer: cleansed, standard column names, comma replaced with dot
    engine_bronze = get_db_engine(MYSQL_DB_BRONZE)
    if engine_bronze is not None:
        try:
            with engine_bronze.connect() as conn:
                conn.execute(
                    sqlalchemy.text(
                        f"""
                        CREATE TABLE IF NOT EXISTS {MYSQL_TABLE} (
                            date DATE NOT NULL,
                            date_buy DATE NOT NULL,
                            id VARCHAR(255) NOT NULL,
                            source_debt VARCHAR(100) NULL,
                            cost DECIMAL(10, 2) NOT NULL,
                            installment DECIMAL(10, 2) NOT NULL,
                            total_installments DECIMAL(10, 2) NOT NULL,
                            source_file VARCHAR(255) NULL,
                            created_at DATETIME NULL
                        );
                        """
                    )
                )
                conn.commit()
        except Exception:  # noqa: BLE001
            pass

        align_table_columns(
            engine_bronze,
            {
                "date": "DATE NOT NULL",
                "date_buy": "DATE NOT NULL",
                "id": "VARCHAR(255) NOT NULL",
                "source_debt": "VARCHAR(100) NULL",
                "cost": "DECIMAL(10, 2) NOT NULL",
                "installment": "DECIMAL(10, 2) NOT NULL",
                "total_installments": "DECIMAL(10, 2) NOT NULL",
                "source_file": "VARCHAR(255) NULL",
                "created_at": "DATETIME NULL",
            },
        )

    # 3. SILVER Layer: enriched business data with categories & motivations
    engine_silver = get_db_engine(MYSQL_DB_SILVER)
    if engine_silver is not None:
        try:
            with engine_silver.connect() as conn:
                conn.execute(
                    sqlalchemy.text(
                        f"""
                        CREATE TABLE IF NOT EXISTS {MYSQL_TABLE} (
                            date DATE NOT NULL,
                            date_buy DATE NOT NULL,
                            id VARCHAR(255) NOT NULL,
                            source_debt VARCHAR(100) NULL,
                            cost DECIMAL(10, 2) NOT NULL,
                            installment DECIMAL(10, 2) NOT NULL,
                            total_installments DECIMAL(10, 2) NOT NULL,
                            category VARCHAR(100) NOT NULL,
                            motivation VARCHAR(255) NULL,
                            categorized_by VARCHAR(50) NULL,
                            source_file VARCHAR(255) NULL,
                            created_at DATETIME NULL
                        );
                        """
                    )
                )
                conn.commit()
        except Exception:  # noqa: BLE001
            pass

        align_table_columns(
            engine_silver,
            {
                "date": "DATE NOT NULL",
                "date_buy": "DATE NOT NULL",
                "id": "VARCHAR(255) NOT NULL",
                "source_debt": "VARCHAR(100) NULL",
                "cost": "DECIMAL(10, 2) NOT NULL",
                "installment": "DECIMAL(10, 2) NOT NULL",
                "total_installments": "DECIMAL(10, 2) NOT NULL",
                "category": "VARCHAR(100) NOT NULL",
                "motivation": "VARCHAR(255) NULL",
                "categorized_by": "VARCHAR(50) NULL",
                "source_file": "VARCHAR(255) NULL",
                "created_at": "DATETIME NULL",
            },
        )


def save_dataframe_replace(df: pd.DataFrame, engine, database_name: str = MYSQL_DB_SILVER) -> None:
    """Safely and atomically replaces all records in MYSQL_TABLE preserving schema and avoiding MySQL Error 1050."""
    if engine is None or df.empty:
        return
    try:
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text(f"DROP TABLE IF EXISTS {MYSQL_TABLE};"))
            conn.commit()
    except Exception:  # noqa: BLE001
        pass

    create_medallion_tables()

    try:
        with engine.connect() as conn:
            df.to_sql(MYSQL_TABLE, con=conn, if_exists="append", index=False)
            conn.commit()
    except Exception:  # noqa: BLE001
        try:
            with engine.connect() as conn:
                df.to_sql(MYSQL_TABLE, con=conn, if_exists="append", index=False)
                conn.commit()
        except Exception:  # noqa: BLE001
            pass


_BRONZE_KEY_COLS = [
    "date",
    "date_buy",
    "id",
    "cost",
    "installment",
    "total_installments",
    "source_debt",
    "source_file",
]


def _bronze_row_key(row) -> str:
    return "_".join(str(row[c]) for c in _BRONZE_KEY_COLS)


def ingest_raw_bronze(parsed_files: list[dict], progress=None) -> dict[str, int]:
    """Persists parsed invoices into the Raw and Bronze layers with Bronze-side deduplication.

    ``parsed_files`` is a list of ``{"filename", "df_raw", "df_bronze"}`` dicts. ``progress`` (if
    given) is called as ``progress(done, total, filename)`` after each file. Keeps the
    composite-key dedup logic in one place for the import tab.
    """
    create_medallion_tables()
    engine_raw = get_db_engine(MYSQL_DB_RAW)
    engine_bronze = get_db_engine(MYSQL_DB_BRONZE)

    raw_inserted = 0
    bronze_inserted = 0
    bronze_skipped = 0

    existing_keys: set[str] = set()
    if engine_bronze is not None:
        with engine_bronze.connect() as conn:
            try:
                existing = pd.read_sql(
                    sqlalchemy.text(f"SELECT {', '.join(_BRONZE_KEY_COLS)} FROM {MYSQL_TABLE}"),
                    conn,
                )
                for _, r in existing.iterrows():
                    existing_keys.add(_bronze_row_key(r))
            except Exception:  # noqa: BLE001
                pass

    total = len(parsed_files)
    for idx, p in enumerate(parsed_files):
        df_r = p["df_raw"]
        df_b = p["df_bronze"]

        if engine_raw is not None and not df_r.empty:
            with engine_raw.connect() as conn_r:
                df_r.to_sql(MYSQL_TABLE, con=conn_r, if_exists="append", index=False)
                conn_r.commit()
            raw_inserted += len(df_r)

        if engine_bronze is not None and not df_b.empty:
            rows_to_insert = []
            for _, row in df_b.iterrows():
                rk = _bronze_row_key(row)
                if rk in existing_keys:
                    bronze_skipped += 1
                else:
                    existing_keys.add(rk)
                    rows_to_insert.append(row)
            if rows_to_insert:
                with engine_bronze.connect() as conn_b:
                    pd.DataFrame(rows_to_insert).to_sql(
                        MYSQL_TABLE, con=conn_b, if_exists="append", index=False
                    )
                    conn_b.commit()
                bronze_inserted += len(rows_to_insert)

        if progress is not None:
            progress(idx + 1, total, p.get("filename", ""))

    clear_caches()
    return {
        "raw_inserted": raw_inserted,
        "bronze_inserted": bronze_inserted,
        "bronze_skipped": bronze_skipped,
    }


def deduplicate_all_layers() -> dict[str, int]:
    """Removes duplicate records across Raw, Bronze, and Silver database layers and returns dropped counts."""
    ensure_databases_exist()
    results = {"raw": 0, "bronze": 0, "silver": 0}

    for db_name, key in [
        (MYSQL_DB_RAW, "raw"),
        (MYSQL_DB_BRONZE, "bronze"),
        (MYSQL_DB_SILVER, "silver"),
    ]:
        eng = get_db_engine(db_name)
        if eng is None:
            continue
        try:
            with eng.connect() as conn:
                df = pd.read_sql(f"SELECT * FROM {MYSQL_TABLE}", conn)
                if df.empty:
                    continue
                before_count = len(df)
                if db_name == MYSQL_DB_RAW:
                    cols = [c for c in df.columns if c != "created_at"]
                    df_clean = df.drop_duplicates(subset=cols, keep="first")
                else:
                    cols = [
                        "date",
                        "date_buy",
                        "id",
                        "cost",
                        "installment",
                        "total_installments",
                        "source_debt",
                        "source_file",
                    ]
                    actual_cols = [c for c in cols if c in df.columns]
                    df_clean = df.drop_duplicates(subset=actual_cols, keep="first")

                after_count = len(df_clean)
                dropped = before_count - after_count
                results[key] = dropped
                if dropped > 0:
                    save_dataframe_replace(df_clean, eng, db_name)
        except Exception:  # noqa: BLE001
            pass

    clear_caches()
    return results


_SILVER_DEDUP_SUBSET = [
    "date",
    "date_buy",
    "id",
    "cost",
    "installment",
    "total_installments",
    "source_debt",
    "source_file",
]


def _shape_silver_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Standardizes a raw Silver-layer frame: load-time dedup, type casting, category coercion,
    merchant-id canonicalization, and the derived analytic / transaction-flag columns that
    ``analytics.py`` and the UI depend on. Pure DataFrame transform — no DB access."""
    if df.empty:
        return df

    # Deduplicate on load
    dup_subset = [c for c in _SILVER_DEDUP_SUBSET if c in df.columns]
    if dup_subset:
        df = df.drop_duplicates(subset=dup_subset, keep="first")

    # Column standardization and type casting
    df["date"] = pd.to_datetime(df["date"])
    df["date_buy"] = pd.to_datetime(df["date_buy"])
    df["cost"] = pd.to_numeric(df["cost"], errors="coerce").fillna(0.0)
    df["installment"] = pd.to_numeric(df["installment"], errors="coerce").fillna(0).astype(int)
    df["total_installments"] = (
        pd.to_numeric(df["total_installments"], errors="coerce").fillna(0).astype(int)
    )
    df["source_debt"] = df["source_debt"].fillna("").astype(str).str.strip()
    df["category"] = df["category"].fillna("not_found").astype(str).str.strip().str.lower()
    df["category"] = df["category"].apply(lambda c: c if c in CATEGORY_CONFIG else "not_found")

    # Collapse configured merchant-name variants to one canonical id (car insurance, fuel
    # app, ...) so their installment series aggregate as a single merchant.
    df["id"] = df["id"].astype(str).map(normalize_merchant_id)

    # Derived analytic columns and payment/refund flags
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["year_month"] = df["date"].dt.strftime("%Y-%m")
    df["buy_year_month"] = df["date_buy"].dt.strftime("%Y-%m")
    df["is_installment"] = (df["total_installments"] > 1) | (df["installment"] > 0)
    df["category_label"] = df["category"].map(CATEGORY_LABELS)
    df["day_of_week"] = df["date_buy"].dt.day_name()
    df["day"] = df["date_buy"].dt.day

    # Transaction type flags
    df["is_payment"] = (
        df["id"]
        .astype(str)
        .str.contains(
            r"PAGAMENTO|PAGTO|PAYMENT|PAGAMENTOS VALIDOS", case=False, regex=True, na=False
        )
    )
    df["is_refund"] = (df["cost"] < 0) & (~df["is_payment"])

    return df


@cache_data(ttl=600)
def load_expenses_data() -> pd.DataFrame:
    """Loads and standardizes enriched expense transactions from the SILVER database layer."""
    create_medallion_tables()
    engine_silver = get_db_engine(MYSQL_DB_SILVER)
    if engine_silver is None:
        return pd.DataFrame()

    try:
        query = sqlalchemy.text(f"SELECT * FROM {MYSQL_TABLE}")
        with engine_silver.connect() as connection:
            df = pd.read_sql(query, connection)

        return _shape_silver_frame(df)
    except Exception as e:  # noqa: BLE001
        notify_error(f"Error loading data from Silver layer MySQL database: {e}")
        return pd.DataFrame()


def load_raw_data() -> pd.DataFrame:
    """Loads records from the RAW database layer."""
    create_medallion_tables()
    engine_raw = get_db_engine(MYSQL_DB_RAW)
    if engine_raw is None:
        return pd.DataFrame()
    try:
        with engine_raw.connect() as conn:
            return pd.read_sql(f"SELECT * FROM {MYSQL_TABLE} ORDER BY created_at DESC", conn)
    except Exception:  # noqa: BLE001
        return pd.DataFrame()


def load_bronze_data() -> pd.DataFrame:
    """Loads records from the BRONZE database layer."""
    create_medallion_tables()
    engine_bronze = get_db_engine(MYSQL_DB_BRONZE)
    if engine_bronze is None:
        return pd.DataFrame()
    try:
        with engine_bronze.connect() as conn:
            return pd.read_sql(f"SELECT * FROM {MYSQL_TABLE} ORDER BY date DESC", conn)
    except Exception:  # noqa: BLE001
        return pd.DataFrame()


def load_silver_data() -> pd.DataFrame:
    """Loads records from the SILVER database layer."""
    create_medallion_tables()
    engine_silver = get_db_engine(MYSQL_DB_SILVER)
    if engine_silver is None:
        return pd.DataFrame()
    try:
        with engine_silver.connect() as conn:
            return pd.read_sql(f"SELECT * FROM {MYSQL_TABLE} ORDER BY date DESC", conn)
    except Exception:  # noqa: BLE001
        return pd.DataFrame()
