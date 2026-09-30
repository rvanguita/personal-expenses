"""Write paths of expenses.database against SQLite engines (no MySQL): Raw/Bronze ingest with
Bronze dedup, cross-layer dedup, and the server-side database bootstrap."""

import datetime
from decimal import Decimal

import pandas as pd
import pytest
import sqlalchemy

from expenses import database
from expenses.config import MYSQL_DB_BRONZE, MYSQL_DB_RAW, MYSQL_DB_SILVER, MYSQL_TABLE
from expenses.parser import parse_raw_csv, transform_raw_to_bronze


def test_bronze_row_key_ignores_storage_types():
    parsed = pd.Series(
        {
            "date": pd.Timestamp("2026-01-05"),
            "date_buy": pd.Timestamp("2025-12-05"),
            "id": "DEMO STORE ",
            "cost": 400.0,
            "installment": 1,
            "total_installments": 3,
            "source_debt": "CARDHOLDER_A",
            "source_file": "Invoice2026-01-05.csv",
        }
    )
    # The same row as MySQL returns it (DATE -> date, DECIMAL(10,2) -> Decimal).
    stored = parsed.copy().astype(object)
    stored["date"] = datetime.date(2026, 1, 5)
    stored["date_buy"] = datetime.date(2025, 12, 5)
    stored["cost"] = Decimal("400.00")
    stored["installment"] = Decimal("1.00")
    stored["total_installments"] = Decimal("3.00")
    assert database._bronze_row_key(parsed) == database._bronze_row_key(stored)
    assert database._key_part("cost", None) == "" and database._key_part("cost", float("nan")) == ""
    assert database._key_part("date", "2026-01-05 00:00:00.000000") == "2026-01-05"  # SQLite text
    assert database._bronze_row_key(parsed) != database._bronze_row_key(
        parsed.replace(400.0, 401.0)
    )


@pytest.fixture
def sqlite_layers(monkeypatch, tmp_path):
    """One SQLite file per medallion layer, served by a stubbed ``get_db_engine``."""
    engines = {
        name: sqlalchemy.create_engine(f"sqlite:///{tmp_path / name}.db")
        for name in (MYSQL_DB_RAW, MYSQL_DB_BRONZE, MYSQL_DB_SILVER)
    }
    monkeypatch.setattr(database, "get_db_engine", lambda name=MYSQL_DB_SILVER: engines[name])
    monkeypatch.setattr(database, "create_medallion_tables", lambda *_a, **_k: None)
    monkeypatch.setattr(database, "ensure_databases_exist", lambda: None)
    yield engines
    for engine in engines.values():
        engine.dispose()


def _rows(engine) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(f"SELECT * FROM {MYSQL_TABLE}", conn)


def _parsed(csv_file) -> dict:
    df_raw = parse_raw_csv(csv_file)
    return {
        "filename": csv_file.name,
        "df_raw": df_raw,
        "df_bronze": transform_raw_to_bronze(df_raw),
    }


def test_ingest_raw_bronze_writes_both_layers_and_dedups_bronze(sqlite_layers, sample_csv_file):
    parsed = _parsed(sample_csv_file)
    progress = []

    first = database.ingest_raw_bronze([parsed], progress=lambda *a: progress.append(a))
    assert first == {
        "raw_inserted": len(parsed["df_raw"]),
        "bronze_inserted": len(parsed["df_bronze"]),
        "bronze_skipped": 0,
    }
    assert progress == [(1, 1, sample_csv_file.name)]

    # Same invoice again: Raw keeps every upload, Bronze skips rows already stored.
    second = database.ingest_raw_bronze([parsed])
    assert second["bronze_inserted"] == 0
    assert second["bronze_skipped"] == len(parsed["df_bronze"])
    assert len(_rows(sqlite_layers[MYSQL_DB_RAW])) == 2 * len(parsed["df_raw"])
    assert len(_rows(sqlite_layers[MYSQL_DB_BRONZE])) == len(parsed["df_bronze"])


def test_ingest_raw_bronze_without_database(monkeypatch, sample_csv_file):
    monkeypatch.setattr(database, "get_db_engine", lambda *_a: None)
    monkeypatch.setattr(database, "create_medallion_tables", lambda *_a, **_k: None)
    result = database.ingest_raw_bronze([_parsed(sample_csv_file)])
    assert result == {"raw_inserted": 0, "bronze_inserted": 0, "bronze_skipped": 0}


def test_deduplicate_all_layers(sqlite_layers, monkeypatch, sample_csv_file):
    parsed = _parsed(sample_csv_file)
    for _ in range(2):
        parsed["df_raw"].to_sql(
            MYSQL_TABLE, sqlite_layers[MYSQL_DB_RAW], if_exists="append", index=False
        )
        parsed["df_bronze"].to_sql(
            MYSQL_TABLE, sqlite_layers[MYSQL_DB_BRONZE], if_exists="append", index=False
        )
    replaced = {}
    monkeypatch.setattr(
        database,
        "save_dataframe_replace",
        lambda df, _engine, name: replaced.setdefault(name, len(df)),
    )

    dropped = database.deduplicate_all_layers()

    assert dropped == {
        "raw": len(parsed["df_raw"]),
        "bronze": len(parsed["df_bronze"]),
        "silver": 0,  # empty / missing table is skipped
    }
    assert replaced == {
        MYSQL_DB_RAW: len(parsed["df_raw"]),
        MYSQL_DB_BRONZE: len(parsed["df_bronze"]),
    }


def test_ensure_databases_exist_skips_without_credentials(monkeypatch):
    monkeypatch.setattr(database, "MYSQL_USER", None)
    monkeypatch.setattr(
        database.sqlalchemy, "create_engine", lambda *_a, **_k: pytest.fail("no engine expected")
    )
    database.ensure_databases_exist()


def test_ensure_databases_exist_creates_the_three_layers(monkeypatch):
    executed = []

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def execute(self, statement):
            executed.append(str(statement))

        def commit(self):
            executed.append("COMMIT")

    class _Engine:
        def connect(self):
            return _Conn()

    for name, value in {
        "MYSQL_USER": "u",
        "MYSQL_PASSWORD": "p",
        "MYSQL_HOST": "h",
        "MYSQL_PORT": 3306,
    }.items():
        monkeypatch.setattr(database, name, value)
    monkeypatch.setattr(database.sqlalchemy, "create_engine", lambda *_a, **_k: _Engine())

    database.ensure_databases_exist()

    assert executed == [
        f"CREATE DATABASE IF NOT EXISTS {MYSQL_DB_RAW};",
        f"CREATE DATABASE IF NOT EXISTS {MYSQL_DB_BRONZE};",
        f"CREATE DATABASE IF NOT EXISTS {MYSQL_DB_SILVER};",
        "COMMIT",
    ]
