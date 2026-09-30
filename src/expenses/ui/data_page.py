"""Data operations (write paths into Raw / Bronze / Silver), kept apart from the dashboard."""

import pandas as pd
import streamlit as st

from src.expenses.ui.style import header
from src.expenses.ui.tabs import (
    render_categorize_tab,
    render_import_tab,
    render_management_tab,
)


def render_data(df_full: pd.DataFrame, engine) -> None:
    header("Dados", "Importar faturas, categorizar e corrigir registros")
    tab_import, tab_categorize, tab_manage = st.tabs(["Importar", "Categorizar", "Gerenciar"])
    with tab_import:
        render_import_tab(engine)
    with tab_categorize:
        render_categorize_tab(engine)
    with tab_manage:
        render_management_tab(df_full, engine)
