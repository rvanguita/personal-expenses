import dash
import dash_mantine_components as dmc
import pandas as pd
from dash import Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate

from src.expenses.analytics import (
    get_future_installments_details,
    get_future_installments_projection,
    get_next_month_commitment_metrics,
)
from src.expenses.config import format_currency_pt
from src.expenses.dash_ui import data
from src.expenses.dash_ui.insights_pt import executive_summary_insight
from src.expenses.dash_ui.render import render_ctx, safe_render
from src.expenses.dash_ui.ui import (
    data_table,
    dynamic_graph,
    empty,
    insight_card,
    kpi,
    kpi_grid,
    panel,
    section,
    two_col,
)
from src.expenses.ui.figures import build_budget_vs_limit_figure, build_future_by_category_figure

dash.register_page(__name__, path="/relatorios", name="Relatórios", title="Relatórios")

R = format_currency_pt
DEFAULT_LIMIT = 5000

layout = dmc.Stack(
    [
        dmc.Group(
            [
                dmc.NumberInput(
                    id="rp-limit",
                    label="🎯 Limite de orçamento de referência (R$)",
                    value=DEFAULT_LIMIT,
                    min=100,
                    step=500,
                    thousandSeparator=".",
                    decimalSeparator=",",
                    w={"base": "100%", "sm": 320},
                ),
                dmc.Button("📥 Baixar CSV", id="rp-download-btn", variant="light", mt=24),
            ],
            align="flex-start",
        ),
        dcc.Download(id="rp-download"),
        html.Div(id="rp-content"),
    ],
    gap="md",
)


def _forecast(df_full: pd.DataFrame, limit: float):
    m = get_next_month_commitment_metrics(df_full, reference_limit=limit)
    projection = get_future_installments_projection(df_full)
    details = get_future_installments_details(df_full)
    if not m["has_data"] or projection.empty:
        return empty("Nenhuma compra parcelada ativa encontrada.")
    over = m["is_over_limit"]
    diff = (
        f"+{R(m['diff_from_limit'])} acima do limite"
        if over
        else f"{R(abs(m['diff_from_limit']))} restantes"
    )
    blocks = [
        panel(
            None,
            kpi_grid(
                kpi(
                    f"🔒 Próximo mês ({m['next_month']})",
                    R(m["next_month_cost"]),
                    f"{m['num_installments']} parcelas ativas",
                    diff,
                    bad=over,
                ),
                kpi(
                    "🎯 % do limite",
                    f"{m['pct_of_limit']:.1f}%",
                    f"Limite: {R(limit)}",
                    "Acima do limite!" if over else "Dentro do orçamento",
                    bad=over,
                ),
                kpi(
                    "💳 Dívida futura em parcelas",
                    R(m["total_future_debt"]),
                    "Soma das parcelas restantes",
                ),
                kpi("🗓️ Horizonte", f"{m['months_count']} meses", f"Até {m['max_future_month']}"),
            ),
        ),
        two_col(
            panel(
                "📊 Orçamento comprometido vs. limite",
                dynamic_graph(build_budget_vs_limit_figure(projection, limit)),
            ),
            panel(
                "🏷️ Compromissos futuros por categoria",
                dynamic_graph(build_future_by_category_figure(details)),
            ),
            ratio="1fr 1fr",
        ),
    ]
    if not details.empty:
        table = pd.DataFrame(
            {
                "Mês de cobrança": details["future_month"],
                "Estabelecimento": details["id"],
                "Categoria": details["category_label"],
                "Data da compra": pd.to_datetime(details["date_buy"]),
                "Parcela": details["installment_display"],
                "Valor": details["cost"].astype(float),
            }
        )
        blocks.append(
            panel(
                "🔍 Parcelas futuras por compra", data_table(table, money=("Valor",), page_size=15)
            )
        )
    return dmc.Stack(blocks, gap="md")


@callback(
    Output("rp-content", "children"),
    Input("filters", "data"),
    Input("theme", "data"),
    Input("hide-switch", "checked"),
    Input("rp-limit", "value"),
    Input("url", "pathname"),
)
@safe_render()
def render(filters, theme, hide, limit, pathname):
    if pathname != "/relatorios":
        raise PreventUpdate
    df_full, df = data.get_frames(filters)
    if df.empty:
        return empty("Nenhum dado selecionado para o relatório.")
    limit = float(limit or DEFAULT_LIMIT)
    table = pd.DataFrame(
        {
            "Data da fatura": pd.to_datetime(df["date"]),
            "Data da compra": pd.to_datetime(df["date_buy"]),
            "Estabelecimento": df["id"],
            "Categoria": df["category_label"],
            "Valor": df["cost"].astype(float),
            "Parcelas": [
                f"{int(i)}/{int(t)}" if t > 1 else "À vista"
                for i, t in zip(df["installment"], df["total_installments"], strict=True)
            ],
        }
    )
    with render_ctx(theme, hide):
        forecast = _forecast(df_full, limit)
    return dmc.Stack(
        [
            section("📑 Relatório executivo"),
            insight_card(executive_summary_insight(df[~df["is_payment"]])),
            section(
                "🔮 Parcelas futuras e orçamento comprometido",
                "Quanto do orçamento futuro já está travado em parcelas, contra o limite de referência.",
            ),
            forecast,
            section("📑 Tabela completa (filtrada)"),
            panel(None, data_table(table, money=("Valor",), page_size=25)),
        ],
        gap="md",
    )


@callback(
    Output("rp-download", "data"),
    Input("rp-download-btn", "n_clicks"),
    State("filters", "data"),
    prevent_initial_call=True,
)
def download(clicks, filters):
    if not clicks or not filters:
        raise PreventUpdate
    _, df = data.get_frames(filters)
    if df.empty:
        raise PreventUpdate
    return data.export_csv(df)
