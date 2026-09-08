import io

import pandas as pd

from src.expenses.parser import parse_expense_csv, parse_raw_csv, transform_raw_to_bronze


def _csv_file(text: str, name: str = "Invoice2026-01-05.csv") -> io.StringIO:
    f = io.StringIO(text)
    f.name = name
    return f


def test_parse_raw_csv(sample_csv_file):
    df_raw = parse_raw_csv(sample_csv_file)
    assert not df_raw.empty
    assert len(df_raw) == 5
    assert "raw_date" in df_raw.columns
    assert "raw_id" in df_raw.columns
    assert "raw_cost" in df_raw.columns
    assert "raw_installment" in df_raw.columns
    assert "source_file" in df_raw.columns


def test_transform_raw_to_bronze(sample_csv_file):
    df_raw = parse_raw_csv(sample_csv_file)
    df_bronze = transform_raw_to_bronze(df_raw)
    assert not df_bronze.empty
    assert len(df_bronze) == 5
    assert "date" in df_bronze.columns
    assert "date_buy" in df_bronze.columns
    assert "id" in df_bronze.columns
    assert "source_debt" in df_bronze.columns
    assert "cost" in df_bronze.columns
    assert "installment" in df_bronze.columns
    assert "total_installments" in df_bronze.columns
    assert "source_file" in df_bronze.columns
    assert df_bronze["cost"].dtype == float


def test_parse_expense_csv(sample_csv_file):
    df = parse_expense_csv(sample_csv_file)
    assert not df.empty
    assert len(df) == 5
    assert "date" in df.columns
    assert "date_buy" in df.columns
    assert "id" in df.columns
    assert "cost" in df.columns
    assert "installment" in df.columns
    assert "total_installments" in df.columns

    # Check invoice date extracted from filename
    assert df["date"].iloc[0] == pd.Timestamp("2026-01-05")

    # Check installment parsing
    installment_row = df[df["id"] == "DEMO STORE"].iloc[0]
    assert installment_row["installment"] == 1
    assert installment_row["total_installments"] == 3
    assert installment_row["cost"] == 1200.00

    # Check negative cost handling (payment/refund)
    payment_row = df[df["id"] == "PAGAMENTO FATURA"].iloc[0]
    assert payment_row["cost"] == -1500.00


def test_portuguese_invoice_csv():
    csv_content = (
        "data;estabelecimento;portador;valor;parcela\n"
        "16/03/2022;EXAMPLE CAFE;CARDHOLDER_A;58,00;-\n"
        "19/03/2022;SAMPLE GROCERY;CARDHOLDER_A;30,56;1 de 3\n"
        "22/03/2022;DEMO CLINIC;CARDHOLDER_A;20,00;-\n"
        "23/03/2022;EXAMPLE RESTAURANT;CARDHOLDER_A;23,50;-\n"
    )
    f = _csv_file(csv_content, name="Invoice2022-04-05.csv")
    df_raw = parse_raw_csv(f)
    df_bronze = transform_raw_to_bronze(df_raw)

    assert len(df_raw) == 4
    # Original columns preserved
    for col in ["data", "estabelecimento", "portador", "valor", "parcela"]:
        assert col in df_raw.columns

    # Bronze transformations
    assert len(df_bronze) == 4
    assert df_bronze["source_debt"].iloc[0] == "CARDHOLDER_A"
    assert df_bronze["cost"].iloc[0] == 58.00
    assert df_bronze["cost"].iloc[1] == 30.56
    assert df_bronze["installment"].iloc[1] == 1
    assert df_bronze["total_installments"].iloc[1] == 3


def test_installment_slash_and_sentinel_parsing():
    f = _csv_file(
        "Data;Estabelecimento;Portador;Valor;Parcela\n"
        "01/12/2025;STORE SLASH;CARDHOLDER_A;R$ 10,00;1/3\n"
        "02/12/2025;STORE DASH;CARDHOLDER_A;R$ 20,00;-\n"
        "03/12/2025;STORE EMPTY;CARDHOLDER_A;R$ 30,00;\n"
    )
    df = transform_raw_to_bronze(parse_raw_csv(f))
    by_id = df.set_index("id")
    assert by_id.loc["STORE SLASH", "installment"] == 1
    assert by_id.loc["STORE SLASH", "total_installments"] == 3
    assert by_id.loc["STORE DASH", "installment"] == 0
    assert by_id.loc["STORE DASH", "total_installments"] == 0
    assert by_id.loc["STORE EMPTY", "installment"] == 0
    assert by_id.loc["STORE EMPTY", "total_installments"] == 0


def test_merchant_id_is_upper_and_stripped():
    f = _csv_file(
        "Data;Estabelecimento;Portador;Valor;Parcela\n01/12/2025;  example bakery  ;CARDHOLDER_A;R$ 5,00;-\n"
    )
    df = transform_raw_to_bronze(parse_raw_csv(f))
    assert df["id"].iloc[0] == "EXAMPLE BAKERY"


def test_english_headers_map_to_bronze_columns():
    f = _csv_file(
        "date;merchant;holder;amount;installment\n"
        "01/12/2025;EXAMPLE ONLINE SHOP;CARDHOLDER_A;R$ 12,34;-\n"
        "02/12/2025;DEMO STREAMING;CARDHOLDER_A;R$ 55,90;1 de 12\n"
    )
    df_raw = parse_raw_csv(f)
    df_bronze = transform_raw_to_bronze(df_raw)
    for col in (
        "date",
        "date_buy",
        "id",
        "source_debt",
        "cost",
        "installment",
        "total_installments",
    ):
        assert col in df_bronze.columns
    assert df_bronze["cost"].iloc[0] == 12.34
    assert df_bronze["id"].iloc[0] == "EXAMPLE ONLINE SHOP"
    assert df_bronze["total_installments"].iloc[1] == 12


def test_filename_without_date_still_parses():
    f = _csv_file(
        "Data;Estabelecimento;Portador;Valor;Parcela\n01/12/2025;EXAMPLE STORE;CARDHOLDER_A;R$ 9,99;-\n",
        name="extrato.csv",
    )
    df = parse_expense_csv(f)
    assert len(df) == 1
    assert pd.notna(df["date"].iloc[0])


def test_transform_raw_to_bronze_empty_frame():
    out = transform_raw_to_bronze(pd.DataFrame())
    assert isinstance(out, pd.DataFrame)
    assert out.empty
    for col in ("date", "date_buy", "id", "cost", "installment", "total_installments"):
        assert col in out.columns
