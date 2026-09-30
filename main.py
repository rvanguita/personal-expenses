# %%
import streamlit as st

from src.expenses.database import get_db_engine, load_expenses_data
from src.expenses.ui import apply_style, render_dashboard, render_data


def main():
    st.set_page_config(page_title="Despesas", page_icon="💳", layout="wide")
    apply_style()

    engine = get_db_engine()
    if engine is None:
        st.error(
            "Configuração do banco não encontrada no `.env`. Verifique `MYSQL_USER`, "
            "`MYSQL_PASSWORD` e `MYSQL_HOST`."
        )
        return

    df_full = load_expenses_data()
    if df_full.empty:
        st.warning(
            "Nenhum dado encontrado. Use a página **Dados** para importar a primeira fatura."
        )

    pages = [
        st.Page(
            lambda: render_dashboard(df_full), title="Dashboard", url_path="dashboard", default=True
        ),
        st.Page(lambda: render_data(df_full, engine), title="Dados", url_path="dados"),
    ]
    st.navigation(pages, position="top").run()


if __name__ == "__main__":
    main()
