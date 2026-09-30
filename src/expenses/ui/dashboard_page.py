"""The single analytic page: how much was spent, where, and what is already committed."""

import pandas as pd
import streamlit as st

from src.expenses.dashboard import (
    DEFAULT_PERIOD,
    PERIOD_LABELS,
    all_figures,
    build_view,
    filter_options,
    kpi_cards,
)
from src.expenses.ui.style import header, section

_CHART_CONFIG = {"displayModeBar": False}


def render_dashboard(df_full: pd.DataFrame) -> None:
    options = filter_options(df_full)
    labels = dict(options["categories"])
    title = st.empty()  # filled once the view (and its subtitle) is known

    col_period, col_holder, col_category = st.columns([1, 1, 2])
    period = col_period.selectbox(
        "Período",
        list(PERIOD_LABELS),
        index=list(PERIOD_LABELS).index(DEFAULT_PERIOD),
        format_func=PERIOD_LABELS.get,
        key="dash_period",
    )
    holders = col_holder.multiselect(
        "Titular", options["holders"], placeholder="Todos", key="dash_holders"
    )
    categories = col_category.multiselect(
        "Categoria",
        list(labels),
        format_func=labels.get,
        placeholder="Todas",
        key="dash_categories",
    )

    view = build_view(df_full, period, holders, categories)
    subtitle = view.period_label
    if view.last_invoice:
        subtitle += f" · última fatura em {view.last_invoice}"
    with title:
        header("Despesas", subtitle)

    if view.is_empty:
        st.info("Nenhuma transação para os filtros selecionados.")
        return

    for col, card in zip(st.columns(4), kpi_cards(view), strict=True):
        col.metric(
            card["label"],
            card["value"],
            delta=card["note"],
            delta_color="off",
            delta_arrow="off",
            help=card["help"],
            border=True,
        )

    figures = all_figures(view)

    with st.container(border=True):
        section("Evolução mensal · média móvel 3 meses")
        st.plotly_chart(figures["monthly"], width="stretch", config=_CHART_CONFIG)

    left, right = st.columns(2)
    with left.container(border=True):
        section("Por categoria")
        st.plotly_chart(figures["categories"], width="stretch", config=_CHART_CONFIG)
    with right.container(border=True):
        section("Top 10 estabelecimentos")
        st.plotly_chart(figures["merchants"], width="stretch", config=_CHART_CONFIG)

    left, right = st.columns(2)
    with left.container(border=True):
        section("Parcelas futuras")
        st.plotly_chart(figures["commitments"], width="stretch", config=_CHART_CONFIG)
    with right.container(border=True):
        section("Maiores compras do período")
        st.dataframe(
            view.largest,
            hide_index=True,
            width="stretch",
            height=360,
            column_config={
                "date_buy": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "id": "Estabelecimento",
                "category_label": "Categoria",
                "cost": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
            },
        )
