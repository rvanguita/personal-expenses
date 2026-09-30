"""Bodies of the secondary tabs: view dict (from `analyses.py`) -> list of Dash components."""

from dash import html

from app.dash.analyses import FREQUENCY_LABELS, MOMENTUM_LABELS, STATUS_LABELS
from app.dash.data import month_label, spend_delta
from app.dash.figures import (
    bands_figure,
    category_history_figure,
    comparison_figure,
    heatmap_figure,
    holders_figure,
    limit_figure,
    ranked_bar_figure,
    split_figure,
    weekday_figure,
    yoy_figure,
)
from app.dash.fmt import LABEL_PT_TO_KEY, brl, integer, pct
from app.dash.layout import card, empty, graph, kpi_row, row, table
from app.dash.theme import category_color
from src.expenses.config import (
    ANOMALY_Z_THRESHOLD,
    RECURRING_MIN_MONTHS,
    UNCATEGORIZED_WARNING_PCT,
)

NO_ROWS = "Nenhuma transação para os filtros selecionados."


# --------------------------------------------------------------------------- Tendências


def trends_page(view: dict) -> list:
    if view["is_empty"]:
        return [empty(NO_ROWS)]
    trend, pop = view["trend"], view["pop"]
    period_note = (
        f"{month_label(pop['current_months'][0])}–{month_label(pop['current_months'][-1])}"
        if pop["has_data"]
        else "sem período anterior"
    )
    cards = [
        {
            "label": "Tendência",
            "value": view["direction"],
            "note": f"{brl(trend['slope_per_month'])} por mês",
            "help": "Reta ajustada aos totais mensais do período selecionado.",
        },
        {
            "label": "Média 3 meses",
            "value": brl(trend["current_avg"]),
            "note": "últimas três faturas",
            "help": "Média móvel das três faturas mais recentes do período.",
        },
        {
            "label": "Projeção próxima fatura",
            "value": brl(trend["projected_next"]),
            "note": "extrapolada da tendência",
            "help": "Valor da reta de tendência no próximo mês.",
        },
        {
            "label": "Período vs anterior",
            "value": brl(pop["current_total"]),
            "note": spend_delta(pop["delta_pct"] if pop["has_data"] else None, "vs anterior")[0],
            "tone": spend_delta(pop["delta_pct"] if pop["has_data"] else None, "")[1],
            "help": f"Período {period_note} contra o mesmo número de meses imediatamente antes.",
        },
    ]
    momentum = view["momentum"].assign(trend=lambda d: d["direction"].map(MOMENTUM_LABELS))
    return [
        kpi_row(cards),
        card(
            "Por categoria · período atual vs anterior",
            graph(comparison_figure(pop)),
            note="Top 10 categorias do período contra o mesmo número de meses antes dele.",
        ),
        card(
            "Mapa de calor · categoria × mês",
            graph(heatmap_figure(view["heatmap"])),
            note="Compras por categoria em cada fatura do período; mais claro = maior gasto.",
        ),
        row(
            card(
                "Mesmos meses · ano atual vs anterior",
                graph(yoy_figure(view["yoy"])),
            ),
            card(
                "Momento das categorias · últimos 3 meses",
                table(
                    momentum,
                    [
                        ("Categoria", "category_label", "category"),
                        ("Direção", "trend", "text"),
                        ("Último mês", "last_month_value", "money"),
                        ("Variação 3M", "pct_change_over_window", "pct"),
                    ],
                    max_rows=12,
                ),
            ),
        ),
    ]


# --------------------------------------------------------------------------- Atenção


def watchlist_page(view: dict) -> list:
    if view["is_empty"]:
        return [empty(NO_ROWS)]
    recurring, anomalies = view["recurring"], view["anomalies"]
    cards = [
        {
            "label": "Custo fixo mensal",
            "value": brl(view["fixed_cost"]),
            "note": f"≈ {brl(view['fixed_cost'] * 12)} por ano",
            "help": "Soma da média mensal das cobranças recorrentes.",
        },
        {
            "label": "Cobranças recorrentes",
            "value": str(len(recurring)),
            "note": f"em {RECURRING_MIN_MONTHS}+ meses com valor estável",
            "help": "Assinaturas, seguros, mensalidades: todo o histórico.",
        },
        {
            "label": "Compras atípicas",
            "value": str(len(anomalies)),
            "note": f"acima de {ANOMALY_Z_THRESHOLD}σ da categoria",
            "help": "Compras muito acima do valor típico da própria categoria, no período.",
        },
        {
            "label": "Sem categoria",
            "value": brl(view["uncategorized_total"]),
            "note": f"{pct(view['uncategorized_pct'])} do gasto do período",
            "tone": "bad" if view["uncategorized_pct"] > UNCATEGORIZED_WARNING_PCT else "neutral",
            "help": "Classifique esses estabelecimentos na aba Categorize do Streamlit.",
        },
    ]
    recurring = recurring.assign(
        status_label=lambda d: d["status"].map(STATUS_LABELS),
        category=lambda d: d["category_label"].map(_label_to_key),
    )
    anomalies = anomalies.assign(
        z=lambda d: d["z_score"].map(lambda z: f"{z:.1f}σ".replace(".", ","))
    )
    frequency = view["frequency"].assign(
        direction_label=lambda d: d["direction"].map(FREQUENCY_LABELS)
    )
    return [
        kpi_row(cards),
        card(
            "Cobranças recorrentes",
            table(
                recurring,
                [
                    ("Estabelecimento", "id", "text"),
                    ("Categoria", "category_label", "category"),
                    ("Média/mês", "avg_monthly_cost", "money"),
                    ("Última", "last_amount", "money"),
                    ("Mês", "last_month", "month"),
                    ("Meses", "months_count", "int"),
                    ("Status", "status_label", "text"),
                ],
            )
            if not recurring.empty
            else empty("Nenhuma cobrança recorrente detectada."),
        ),
        row(
            card(
                "Compras atípicas",
                table(
                    anomalies,
                    [
                        ("Data", "date_buy", "date"),
                        ("Estabelecimento", "id", "text"),
                        ("Categoria", "category_label", "category"),
                        ("Valor", "cost", "money"),
                        ("Média cat.", "category_avg", "money"),
                        ("Desvio", "z", "text"),
                    ],
                    max_rows=15,
                )
                if not anomalies.empty
                else empty("Nada fora do padrão no período."),
            ),
            card(
                "Sem categoria",
                table(
                    view["uncategorized"],
                    [
                        ("Estabelecimento", "id", "text"),
                        ("Compras", "tx", "int"),
                        ("Total", "total", "money"),
                        ("Última", "last", "date"),
                    ],
                    max_rows=15,
                )
                if not view["uncategorized"].empty
                else empty("Tudo categorizado no período."),
            ),
        ),
        card(
            "Estabelecimentos novos no período",
            table(
                view["new_merchants"],
                [
                    ("Estabelecimento", "id", "text"),
                    ("Categoria", "category_label", "category"),
                    ("Primeira compra", "first", "date"),
                    ("Compras", "tx", "int"),
                    ("Total", "total", "money"),
                ],
                max_rows=15,
            )
            if not view["new_merchants"].empty
            else empty("Nenhum estabelecimento novo (ou o período começa no início do histórico)."),
            note="Primeira compra de todo o histórico caiu dentro do período selecionado.",
        ),
        card(
            "Mudança de frequência",
            table(
                frequency,
                [
                    ("Estabelecimento", "id", "text"),
                    ("Categoria", "category_label", "text"),
                    ("Recente (compras/mês)", "recent_monthly_rate", "rate"),
                    ("Base (compras/mês)", "baseline_monthly_rate", "rate"),
                    ("Variação", "change_pct", "pct"),
                    ("", "direction_label", "text"),
                ],
                max_rows=15,
            )
            if not frequency.empty
            else empty("Sem histórico suficiente para comparar frequência."),
            note="Últimos 2 meses contra os 6 anteriores; variações acima de 50%.",
        ),
    ]


def _label_to_key(label: str) -> str:
    return LABEL_PT_TO_KEY.get(label, "not_found")


# --------------------------------------------------------------------------- Categorias


def category_page(view: dict) -> list:
    if view["is_empty"]:
        return [empty(NO_ROWS)]
    key = view["selected"]
    cards = [
        {
            "label": "Total",
            "value": brl(view["total"]),
            "note": spend_delta(view["momentum_pct"], "em 3 meses")[0],
            "tone": spend_delta(view["momentum_pct"], "")[1],
            "help": "Variação compara o último mês com três meses antes.",
        },
        {
            "label": "Participação",
            "value": pct(view["share_pct"]),
            "note": "do gasto do período",
            "help": "Parcela do gasto (compras positivas) do período nesta categoria.",
        },
        {
            "label": "Compras",
            "value": integer(view["count"]),
            "note": view["label"],
            "help": "Quantidade de compras da categoria no período.",
        },
        {
            "label": "Ticket médio",
            "value": brl(view["avg_ticket"]),
            "note": "por compra",
            "help": "Total da categoria dividido pelo número de compras.",
        },
    ]
    merchants = view["merchants"]
    largest = view["largest"].assign(
        parcelas=lambda d: [
            f"{int(i)}/{int(t)}" if t > 1 else "À vista"
            for i, t in zip(d["installment"], d["total_installments"], strict=True)
        ]
    )
    return [
        kpi_row(cards),
        row(
            card("Histórico mensal", graph(category_history_figure(view["history"], key))),
            card(
                "Principais estabelecimentos",
                graph(
                    ranked_bar_figure(
                        merchants, "id", "cost", [category_color(key)] * len(merchants), height=320
                    )
                ),
            ),
        ),
        card(
            "Maiores compras",
            table(
                largest,
                [
                    ("Data", "date_buy", "date"),
                    ("Estabelecimento", "id", "text"),
                    ("Parcelas", "parcelas", "text"),
                    ("Valor", "cost", "money"),
                ],
            ),
        ),
    ]


# --------------------------------------------------------------------------- Relatórios


def reports_page(view: dict) -> list:
    metrics, limit = view["metrics"], view["limit"]
    if metrics["has_data"]:
        over = metrics["is_over_limit"]
        diff = brl(abs(metrics["diff_from_limit"]))
        cards = [
            {
                "label": f"Parcelas {month_label(metrics['next_month'])}",
                "value": brl(metrics["next_month_cost"]),
                "note": f"{diff} acima do limite" if over else f"{diff} livres no limite",
                "tone": "bad" if over else "good",
                "help": f"{metrics['num_installments']} parcelas já contratadas para a próxima fatura.",
            },
            {
                "label": "Uso do limite",
                "value": pct(metrics["pct_of_limit"], 0),
                "note": f"limite de {brl(limit)}",
                "help": "Definido por REFERENCE_BUDGET_LIMIT no .env.",
            },
            {
                "label": "Total a pagar em parcelas",
                "value": brl(metrics["total_future_debt"]),
                "note": f"em {metrics['months_count']} meses",
                "help": f"Última parcela em {month_label(metrics['max_future_month'])}.",
            },
            {
                "label": "Transações na seleção",
                "value": integer(view["rows"]),
                "note": "exportáveis em CSV abaixo",
                "help": "Linhas do período e filtros atuais (sem pagamentos de fatura).",
            },
        ]
        commitments = [
            kpi_row(cards),
            row(
                card("Parcelas por mês vs limite", graph(limit_figure(view["projection"], limit))),
                card(
                    "Próximas parcelas",
                    html_scroll(
                        table(
                            view["details"],
                            [
                                ("Fatura", "future_month", "month"),
                                ("Estabelecimento", "id", "text"),
                                ("Parcela", "installment_display", "text"),
                                ("Valor", "cost", "money"),
                            ],
                        )
                    ),
                ),
            ),
        ]
    else:
        commitments = [card("Parcelas", empty("Nenhuma compra parcelada em aberto."))]

    invoices = (
        table(
            view["invoices"],
            [
                ("Fatura", "year_month", "month"),
                ("Compras", "tx", "int"),
                ("Bruto", "gross", "money"),
                ("Estornos", "refunds", "money"),
                ("Líquido", "net", "money"),
            ],
        )
        if not view["invoices"].empty
        else empty(NO_ROWS)
    )
    return [*commitments, card("Totais por fatura", invoices)]


def html_scroll(child) -> html.Div:
    return html.Div(child, className="pe-scroll")


# --------------------------------------------------------------------------- Hábitos


def habits_page(view: dict) -> list:
    if view["is_empty"]:
        return [empty(NO_ROWS)]
    cards = [
        {
            "label": "Compras por mês",
            "value": f"{view['per_month']:.0f}",
            "note": f"{integer(view['count'])} compras no período",
            "help": "Número de compras (sem estornos) dividido pelo número de faturas.",
        },
        {
            "label": "Ticket médio",
            "value": brl(view["avg_ticket"]),
            "note": f"mediana {brl(view['median_ticket'])}",
            "help": "Média e mediana do valor por compra; mediana bem abaixo da média indica "
            "poucas compras grandes puxando o total.",
        },
        {
            "label": "Parcelado",
            "value": pct(view["installment_share"]),
            "note": "do valor das compras",
            "help": "Participação das compras parceladas no valor total do período.",
        },
        {
            "label": "Concentração",
            "value": pct(view["top10_share"]),
            "note": f"nos 10 maiores · {view['pareto_n']} de {view['merchants']} fazem 80%",
            "help": "Quanto do gasto está nos 10 estabelecimentos com maior valor, e quantos "
            "estabelecimentos somam 80% do gasto.",
        },
    ]
    return [
        kpi_row(cards),
        row(
            card(
                "À vista vs parcelado",
                graph(split_figure(view["split"])),
                note="Valor das compras por fatura, separado pela forma de pagamento.",
            ),
            card(
                "Faixas de valor",
                graph(bands_figure(view["bands"])),
                note="Quanto do gasto vem de compras pequenas, médias e grandes.",
            ),
        ),
        row(
            card(
                "Dia da semana",
                graph(weekday_figure(view["weekday"])),
                note="Pela data da compra; o dia de maior gasto em destaque.",
            ),
            card(
                "Por titular",
                graph(holders_figure(view["holders"])),
                note="Compras de cada titular do cartão por fatura.",
            ),
        ),
    ]
