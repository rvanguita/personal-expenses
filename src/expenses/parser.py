import io
import re
from datetime import UTC, date, datetime

import pandas as pd

from src.expenses.runtime import notify_error


def parse_raw_csv(file_obj, fallback_date: date | None = None) -> pd.DataFrame:
    """Parses an uploaded CSV file, collecting all raw columns and preserving exact source strings for the RAW layer."""
    try:
        content = file_obj.read()
        if isinstance(content, bytes):
            content_str = content.decode("utf-8", errors="replace")
        else:
            content_str = str(content)

        if hasattr(file_obj, "seek"):
            file_obj.seek(0)

        first_line = content_str.split("\n")[0] if content_str else ""
        sep = ";" if ";" in first_line else ","
        df_raw_csv = pd.read_csv(io.StringIO(content_str), sep=sep, dtype=str)

        if df_raw_csv.empty:
            return pd.DataFrame()

        # Clean column names (strip quotes/spaces)
        df_raw_csv.columns = [
            str(c).strip().replace('"', "").replace("'", "") for c in df_raw_csv.columns
        ]

        # Extract invoice date from filename or fallback
        filename = getattr(file_obj, "name", "invoice_upload.csv")
        date_match = re.search(r"\d{4}-\d{2}-\d{2}", filename)
        if date_match:
            invoice_date = pd.to_datetime(date_match.group()).date()
        elif fallback_date:
            invoice_date = fallback_date
        else:
            invoice_date = datetime.now(tz=UTC).date()

        # Initialize raw output dataframe preserving all original columns from the CSV
        df_raw_output = pd.DataFrame()
        for col in df_raw_csv.columns:
            clean_col = col.lower().strip().replace(" ", "_")
            df_raw_output[clean_col] = df_raw_csv[col].fillna("")

        # Build column mapping dictionary (lowercased stripped names)
        col_map = {col.lower().strip(): col for col in df_raw_csv.columns}

        def get_col_val(candidate_keywords: list[str]) -> pd.Series:
            for kw in candidate_keywords:
                for col_lower, original_col in col_map.items():
                    if kw in col_lower:
                        return df_raw_csv[original_col].fillna("")
            return pd.Series([""] * len(df_raw_csv))

        # Guarantee standard raw_* columns
        df_raw_output["raw_date"] = get_col_val(["data", "date"])
        df_raw_output["raw_id"] = get_col_val(
            [
                "estabelecimento",
                "descricao",
                "descrição",
                "titulo",
                "título",
                "merchant",
                "id",
                "local",
            ]
        )
        df_raw_output["raw_portador"] = get_col_val(
            ["portador", "cartao", "cartão", "holder", "card", "source_debt"]
        )
        df_raw_output["raw_cost"] = get_col_val(
            ["valor", "cost", "amount", "total", "preço", "preco"]
        )
        df_raw_output["raw_installment"] = get_col_val(["parcela", "installment", "parcelas"])

        # Add audit metadata
        df_raw_output["invoice_date"] = invoice_date
        df_raw_output["source_file"] = filename
        df_raw_output["created_at"] = datetime.now(tz=UTC)

        return df_raw_output
    except Exception as e:  # noqa: BLE001
        notify_error(f"Error parsing raw CSV file: {e}")
        return pd.DataFrame()


def transform_raw_to_bronze(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Transforms raw records into standardized BRONZE schema (renamed columns, comma to dot)."""
    if df_raw.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "date_buy",
                "id",
                "source_debt",
                "cost",
                "installment",
                "total_installments",
                "source_file",
            ]
        )

    df_bronze = pd.DataFrame()

    # Invoice date
    if "invoice_date" in df_raw.columns:
        df_bronze["date"] = pd.to_datetime(df_raw["invoice_date"])
    else:
        df_bronze["date"] = pd.to_datetime(datetime.now(tz=UTC).date())

    # Purchase date (checks 'raw_date' or 'data')
    date_col = (
        df_raw["raw_date"]
        if "raw_date" in df_raw.columns
        else df_raw.get("data", df_bronze["date"])
    )
    df_bronze["date_buy"] = pd.to_datetime(date_col, dayfirst=True, errors="coerce").fillna(
        df_bronze["date"]
    )

    # Standardize merchant ID and cardholder
    id_col = df_raw["raw_id"] if "raw_id" in df_raw.columns else df_raw.get("estabelecimento", "")
    df_bronze["id"] = id_col.fillna("").astype(str).str.strip().str.upper()

    portador_col = (
        df_raw["raw_portador"] if "raw_portador" in df_raw.columns else df_raw.get("portador", "")
    )
    df_bronze["source_debt"] = portador_col.fillna("").astype(str).str.strip()

    # Clean monetary values: replace comma with dot, remove currency symbols and whitespace
    cost_col = df_raw["raw_cost"] if "raw_cost" in df_raw.columns else df_raw.get("valor", "0")
    cost_series = (
        cost_col.astype(str)
        .str.replace("R$", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip()
    )
    df_bronze["cost"] = pd.to_numeric(cost_series, errors="coerce").fillna(0.0)

    # Parse installments: "1 de 3" -> 1 and 3, "1/3" -> 1 and 3, "-" -> 0 and 0
    parcela_col = (
        df_raw["raw_installment"]
        if "raw_installment" in df_raw.columns
        else df_raw.get("parcela", "0")
    )
    parcela_clean = (
        parcela_col.astype(str).replace({"-": "0", "nan": "0", "None": "0", "": "0"}).fillna("0")
    )
    split_cols = parcela_clean.str.replace("/", " de ", regex=False).str.split(" de ", expand=True)
    df_bronze["installment"] = (
        pd.to_numeric(split_cols.iloc[:, 0], errors="coerce").fillna(0).astype(int)
        if split_cols.shape[1] > 0
        else 0
    )
    df_bronze["total_installments"] = (
        pd.to_numeric(split_cols.iloc[:, 1], errors="coerce").fillna(0).astype(int)
        if split_cols.shape[1] > 1
        else 0
    )
    df_bronze["source_file"] = df_raw.get("source_file", "")

    return df_bronze[
        [
            "date",
            "date_buy",
            "id",
            "source_debt",
            "cost",
            "installment",
            "total_installments",
            "source_file",
        ]
    ].dropna(subset=["id"])


def parse_expense_csv(file_obj, fallback_date: date | None = None) -> pd.DataFrame:
    """Convenience pipeline: parses CSV directly to Bronze schema."""
    df_raw = parse_raw_csv(file_obj, fallback_date)
    return transform_raw_to_bronze(df_raw)
