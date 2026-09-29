import dash
import dash_mantine_components as dmc
import pandas as pd
from dash import Input, Output, callback, html
from dash.exceptions import PreventUpdate

from src.expenses.analytics import (
    get_category_momentum,
    get_merchant_frequency_change,
    get_period_over_period_comparison,
    get_recurring_merchants,
    get_spending_anomalies,
    get_spending_trend,
    get_year_over_year_comparison,
)
from src.expenses.config import (
    ANOMALY_MIN_CATEGORY_TX,
    ANOMALY_Z_THRESHOLD,
    RECURRING_MAX_CV,
    RECURRING_MIN_MONTHS,
    format_currency_pt,
)
from src.expenses.dash_ui import data
from src.expenses.dash_ui.insights_pt import (
    anomalies_insight,
    frequency_change_insight,
    top_momentum_insight,
)
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
)
from src.expenses.ui.figures import (
    build_period_comparison_figure,
    build_trend_figure,
    build_yoy_figure,
)

dash.register_page(__name__, path="/tendencias", name="Tendências", title="Tendências")

R = format_currency_pt
_DIRECTION = {"up": "📈 Subindo", "down": "📉 Caindo", "stable": "⚖️ Estável"}
_ICON = {"rising": "▲ Em alta", "falling": "▼ Em queda", "stable": "→ Estável"}

layout = html.Div(id="tr-content")


def _trend(df_expenses):
    t = get_spending_trend(df_expenses, group_col="year_month")
    if not t["has_data"]:
        return empty("Ainda não há meses suficientes para calcular a tendência.")
    return panel(
        None,
        kpi_grid(
            kpi(
                "Direção da tendência",
                _DIRECTION[t["direction"]],
                "Regressão linear no período visível",
            ),
            kpi("Média móvel 3 meses", R(t["current_avg"]), "Nível recente suavizado"),
            kpi(
                "Projeção do próximo mês",
                R(t["projected_next"]),
                "Projeção pela linha de tendência",
            ),
            cols=3,
        ),
        dynamic_graph(
            build_trend_figure(t["moving_avg_df"]), "Meses insuficientes para o gráfico."
        ),
    )


def _period(df_filtered, df_full):
    months = sorted(df_filtered["year_month"].dropna().unique().tolist())
    p = get_period_over_period_comparison(df_full, months)
    if not p["has_data"]:
        return empty("Não há histórico anterior suficiente para comparar.")
    cur, prev = p["current_months"], p["previous_months"]
    return panel(
        None,
        kpi_grid(
            kpi(f"Período atual ({len(cur)} m)", R(p["current_total"]), f"{cur[0]} → {cur[-1]}"),
            kpi(
                f"Período anterior ({len(prev)} m)",
                R(p["previous_total"]),
                f"{prev[0]} → {prev[-1]}",
            ),
            kpi(
                "Variação",
                R(p["delta"]),
                "Atual vs. anterior",
                f"{p['delta_pct']:+.1f}%",
                bad=(p["delta"] > 0) if p["delta"] else None,
            ),
            cols=3,
        ),
        dynamic_graph(build_period_comparison_figure(p)),
    )


def _momentum(df_full):
    m = get_category_momentum(df_full, window=3)
    if m.empty:
        return empty("Histórico insuficiente (precisa de 3+ meses por categoria).")
    table = pd.DataFrame(
        {
            "Categoria": m["category_label"],
            "Tendência": m["direction"].map(_ICON),
            "Último mês": m["last_month_value"].astype(float),
            "Variação 3 meses (%)": m["pct_change_over_window"].astype(float),
        }
    )
    return panel(
        None,
        insight_card(top_momentum_insight(m)),
        data_table(table, money=("Último mês",), decimal=("Variação 3 meses (%)",)),
    )


def _yoy(df_full):
    y = get_year_over_year_comparison(df_full)
    if y.empty:
        return empty("A comparação anual precisa de ao menos dois anos de faturas.")
    cur_year, prev_year = int(y["current_year"].iloc[0]), int(y["previous_year"].iloc[0])
    cur, prev = float(y["current_val"].sum()), float(y["previous_val"].sum())
    pct = ((cur - prev) / prev * 100) if prev else 0.0
    return panel(
        None,
        kpi_grid(
            kpi(f"{cur_year} (atual)", R(cur), f"{len(y)} mês(es) em comum"),
            kpi(f"{prev_year} (anterior)", R(prev), "Mesmos meses, ano anterior"),
            kpi(
                "Variação",
                R(cur - prev),
                "Ano contra ano",
                f"{pct:+.1f}%",
                bad=(cur > prev) if cur != prev else None,
            ),
            cols=3,
        ),
        dynamic_graph(build_yoy_figure(y)),
    )


def _recurring(df_full):
    r = get_recurring_merchants(df_full, min_months=RECURRING_MIN_MONTHS, max_cv=RECURRING_MAX_CV)
    if r.empty:
        return empty(
            "Nenhuma assinatura recorrente detectada (precisa de 3+ meses de cobrança estável)."
        )
    total = float(r["avg_monthly_cost"].sum())
    table = pd.DataFrame(
        {
            "Estabelecimento": r["id"],
            "Categoria": r["category_label"],
            "Meses ativos": r["months_count"],
            "Custo médio mensal": r["avg_monthly_cost"],
            "Última cobrança": r["last_amount"],
            "Último mês": r["last_month"],
            "Situação": r["status"].map(
                {"Increased": "🔺 Subiu", "Decreased": "🔻 Caiu", "Stable": "✅ Estável"}
            ),
        }
    )
    return panel(
        None,
        kpi_grid(
            kpi("Custo fixo mensal estimado", R(total)),
            kpi("Recorrentes detectados", f"{len(r)}"),
            kpi("Impacto anual estimado", R(total * 12)),
            cols=3,
        ),
        data_table(
            table, money=("Custo médio mensal", "Última cobrança"), integer=("Meses ativos",)
        ),
    )


def _frequency(df_full):
    f = get_merchant_frequency_change(df_full)
    if f.empty:
        return empty(
            "Nenhuma mudança relevante de frequência (precisa de histórico para a linha de base)."
        )
    table = pd.DataFrame(
        {
            "Estabelecimento": f["id"],
            "Categoria": f["category_label"],
            "Ritmo recente (tx/mês)": f["recent_monthly_rate"].astype(float),
            "Ritmo histórico (tx/mês)": f["baseline_monthly_rate"].astype(float),
            "Mudança": f["direction"].map({"increased": "🔺 Aumentou", "decreased": "🔻 Diminuiu"}),
            "Variação (%)": f["change_pct"].astype(float),
        }
    )
    return panel(
        None,
        insight_card(frequency_change_insight(f)),
        data_table(
            table, decimal=("Ritmo recente (tx/mês)", "Ritmo histórico (tx/mês)", "Variação (%)")
        ),
    )


def _anomalies(df_expenses):
    a = get_spending_anomalies(
        df_expenses, z_threshold=ANOMALY_Z_THRESHOLD, min_category_tx=ANOMALY_MIN_CATEGORY_TX
    )
    children = [insight_card(anomalies_insight(a))]
    if not a.empty:
        children.append(
            data_table(
                pd.DataFrame(
                    {
                        "Data da compra": pd.to_datetime(a["date_buy"]),
                        "Estabelecimento": a["id"],
                        "Categoria": a["category_label"],
                        "Valor": a["cost"].astype(float),
                        "Média da categoria": a["category_avg"].astype(float),
                        "Desvio": a["z_score"].apply(lambda z: f"{z:.1f}σ acima da média"),
                    }
                ),
                money=("Valor", "Média da categoria"),
            )
        )
    return panel(None, *children)


@callback(
    Output("tr-content", "children"),
    Input("filters", "data"),
    Input("theme", "data"),
    Input("hide-switch", "checked"),
    Input("url", "pathname"),
)
@safe_render()
def render(filters, theme, hide, pathname):
    if pathname != "/tendencias":
        raise PreventUpdate
    df_full, df_f = data.get_frames(filters)
    if df_f.empty:
        return empty("Nenhuma transação com os filtros selecionados.")
    df_expenses = df_f[~df_f["is_payment"]]
    with render_ctx(theme, hide):
        return dmc.Stack(
            [
                section("🔮 Tendência e projeção do próximo mês"),
                _trend(df_expenses),
                section(
                    "⏮️ Período contra período",
                    "Compara as faturas selecionadas com o período imediatamente anterior, de mesmo tamanho.",
                ),
                _period(df_f, df_full),
                section(
                    "🧭 Momento das categorias (3 meses)",
                    "Categorias com tendência consistente de alta ou queda.",
                ),
                _momentum(df_full),
                section("📆 Ano contra ano"),
                _yoy(df_full),
                section(
                    "🔁 Assinaturas e custos fixos",
                    "Estabelecimentos cobrados de forma estável em vários meses.",
                ),
                _recurring(df_full),
                section(
                    "🔀 Mudança de frequência",
                    "Estabelecimentos cujo ritmo recente de compras mudou frente ao histórico.",
                ),
                _frequency(df_full),
                section(
                    "⚠️ Transações incomuns",
                    "Compras muito acima do padrão estatístico da categoria.",
                ),
                _anomalies(df_expenses),
            ],
            gap="md",
        )
