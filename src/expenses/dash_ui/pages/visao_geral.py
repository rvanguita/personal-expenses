import dash
import dash_mantine_components as dmc
import pandas as pd
from dash import Input, Output, State, callback, callback_context, html
from dash.exceptions import PreventUpdate

from src.expenses.analytics import calculate_kpis
from src.expenses.config import LABEL_TO_CAT, REFERENCE_BUDGET_LIMIT, format_currency_pt
from src.expenses.dash_ui import data
from src.expenses.dash_ui.insights_pt import automated_insights, health_insight, next_month_insight
from src.expenses.dash_ui.render import render_ctx, safe_render
from src.expenses.dash_ui.ui import (
    data_table,
    empty,
    fig_or_empty,
    graph,
    insight_stack,
    kpi,
    kpi_grid,
    panel,
    section,
    two_col,
)
from src.expenses.ui.figures import (
    build_category_distribution_figure,
    build_day_of_week_figure,
    build_monthly_evolution_figure,
    build_top_merchants_figure,
)

dash.register_page(__name__, path="/", name="Visão geral", title="Visão geral")

R = format_currency_pt

layout = dmc.Stack(
    [
        html.Div(id="ov-banners"),
        section("💡 Insights automáticos"),
        html.Div(id="ov-insights"),
        section("📊 Indicadores-chave"),
        html.Div(id="ov-kpis"),
        panel("📋 Totais por fatura", html.Div(id="ov-invoices")),
        two_col(
            panel(
                "📊 Evolução mensal por categoria",
                dmc.Group(
                    [
                        dmc.SegmentedControl(
                            id="ov-timeline",
                            value="year_month",
                            data=[
                                {"value": "year_month", "label": "Data da fatura"},
                                {"value": "buy_year_month", "label": "Data da compra"},
                            ],
                            size="xs",
                        ),
                        dmc.SegmentedControl(
                            id="ov-style",
                            value="stacked",
                            data=[
                                {"value": "stacked", "label": "Empilhado"},
                                {"value": "lines", "label": "Linhas"},
                            ],
                            size="xs",
                        ),
                    ],
                    gap="md",
                ),
                graph(id="ov-monthly"),
                subtitle="Clique em um mês para filtrar a página.",
            ),
            panel(
                "🏆 Gasto por categoria",
                graph(id="ov-cats"),
                subtitle="Clique em uma categoria para filtrar a página.",
            ),
        ),
        two_col(
            panel("🏢 Top 10 estabelecimentos", graph(id="ov-merchants")),
            panel("📅 Gasto por dia da semana", graph(id="ov-dow")),
        ),
    ],
    gap="md",
)


def _invoice_table(df_expenses: pd.DataFrame) -> pd.DataFrame:
    s = (
        df_expenses.groupby(["year_month", "date"])
        .agg(
            n=("cost", "count"),
            gross=("cost", lambda x: x[x > 0].sum()),
            refunds=("cost", lambda x: x[x < 0].sum()),
            net=("cost", "sum"),
        )
        .reset_index()
        .sort_values("date", ascending=False)
    )
    return pd.DataFrame(
        {
            "Mês": s["year_month"],
            "Data da fatura": pd.to_datetime(s["date"]),
            "Transações": s["n"].astype(int),
            "Compras brutas": s["gross"].astype(float),
            "Estornos": s["refunds"].astype(float),
            "Total líquido": s["net"].astype(float),
        }
    )


@callback(
    Output("ov-banners", "children"),
    Output("ov-insights", "children"),
    Output("ov-kpis", "children"),
    Output("ov-invoices", "children"),
    Output("ov-monthly", "figure"),
    Output("ov-cats", "figure"),
    Output("ov-merchants", "figure"),
    Output("ov-dow", "figure"),
    Input("filters", "data"),
    Input("selection", "data"),
    Input("theme", "data"),
    Input("hide-switch", "checked"),
    Input("ov-timeline", "value"),
    Input("ov-style", "value"),
    Input("url", "pathname"),
)
@safe_render(n_outputs=8)
def render(filters, selection, theme, hide, timeline, style, pathname):
    if pathname != "/":
        raise PreventUpdate
    selection = selection or {}
    month, category = selection.get("month"), selection.get("category")
    month_col = selection.get("month_col", "year_month")

    df_full, df_f = data.get_frames(filters)
    if df_f.empty:
        nothing = fig_or_empty(None)
        return (
            None,
            empty("Nenhuma transação com os filtros selecionados."),
            None,
            None,
            nothing,
            nothing,
            nothing,
            nothing,
        )

    def expenses(df):
        return df[~df["is_payment"]]

    df_sel = data.apply_selection(df_f, month, category, month_col)
    df_for_months = data.apply_selection(df_f, category=category)  # monthly chart keeps all months
    df_for_cats = data.apply_selection(
        df_f, month=month, month_col=month_col
    )  # category chart keeps all categories
    if df_sel.empty:
        message = empty("A seleção não retornou transações. Limpe o filtro por clique.")
        nothing = fig_or_empty(None)
        return None, message, None, None, nothing, nothing, nothing, nothing

    exp_sel = expenses(df_sel)
    kpis = calculate_kpis(df_sel, df_full)

    with render_ctx(theme, hide):
        fig_monthly = fig_or_empty(
            build_monthly_evolution_figure(
                expenses(df_for_months), group_col=timeline, chart_style=style, height=420
            )
        )
        fig_cats = fig_or_empty(
            build_category_distribution_figure(expenses(df_for_cats), height=420)
        )
        fig_merchants = fig_or_empty(build_top_merchants_figure(exp_sel))
        fig_dow = fig_or_empty(build_day_of_week_figure(exp_sel, height=390))

    banners = insight_stack(
        [
            health_insight(df_full),
            next_month_insight(df_full, reference_limit=REFERENCE_BUDGET_LIMIT),
        ]
    )
    refunds_caption = (
        f"Bruto: {R(kpis['gross_spent'])} · Estornos: {R(kpis['total_refunds'])}"
        if kpis["total_refunds"] < 0
        else f"{kpis['num_months']} fatura(s) selecionada(s)"
    )
    delta = kpis["mom_delta_pct"]
    tiles = kpi_grid(
        kpi("💰 Gasto líquido", R(kpis["total_spent"]), refunds_caption),
        kpi("📅 Média mensal", R(kpis["avg_monthly_spent"]), "Média líquida por fatura"),
        kpi(
            "📈 Variação mensal",
            R(kpis["latest_m_val"]),
            "Última vs. anterior",
            f"{delta:+.1f}% ({R(kpis['mom_delta_val'])})",
            bad=(delta > 0) if delta else None,
        ),
        kpi(
            "🏆 Maior categoria",
            kpis["top_cat_name"],
            f"{R(kpis['top_cat_val'])} ({kpis['top_cat_pct']:.1f}%)",
        ),
        kpi(
            "🧾 Transações",
            f"{kpis['total_tx']:,}".replace(",", "."),
            f"Ticket médio: {R(kpis['avg_tx'])}",
        ),
        kpi(
            "💳 Parcelado",
            f"{kpis['installment_pct']:.1f}%",
            f"{R(kpis['installment_spent'])} no total",
        ),
        cols=3,
    )
    insights = insight_stack(automated_insights(kpis, exp_sel, df_full), cols=3)
    invoices = data_table(
        _invoice_table(exp_sel),
        money=("Compras brutas", "Estornos", "Total líquido"),
        integer=("Transações",),
    )
    return banners, insights, tiles, invoices, fig_monthly, fig_cats, fig_merchants, fig_dow


def next_selection(trigger, month_click, cat_click, selection, timeline) -> dict:
    """Cross-filter state after a click on a month/category bar; clicking it again clears it."""
    selection = dict(selection or {})
    if trigger == "ov-monthly" and month_click:
        month = month_click["points"][0].get("x")
        same = selection.get("month") == month and selection.get("month_col") == timeline
        selection.pop("month", None)
        selection.pop("month_col", None)
        if month and not same:
            selection |= {"month": month, "month_col": timeline}
    elif trigger == "ov-cats" and cat_click:
        category = LABEL_TO_CAT.get(cat_click["points"][0].get("y"))
        if not category:
            raise PreventUpdate
        if selection.get("category") == category:
            selection.pop("category")
        else:
            selection["category"] = category
    else:
        raise PreventUpdate
    return selection


@callback(
    Output("selection", "data", allow_duplicate=True),
    Input("ov-monthly", "clickData"),
    Input("ov-cats", "clickData"),
    State("selection", "data"),
    State("ov-timeline", "value"),
    prevent_initial_call=True,
)
def pick(month_click, cat_click, selection, timeline):
    return next_selection(
        callback_context.triggered_id, month_click, cat_click, selection, timeline
    )
