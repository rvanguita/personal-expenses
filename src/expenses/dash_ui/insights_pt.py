"""Insights do Dash em pt-BR.

Mesma lógica e limiares do ``ui/insights.py`` (que serve o Streamlit em inglês) — os números vêm
de ``analytics`` e ``config``; aqui só o texto é próprio do Dash.
"""

import pandas as pd

from src.expenses.analytics import (
    get_financial_health_score,
    get_month_pace_projection,
    get_next_month_commitment_metrics,
    get_spending_anomalies,
)
from src.expenses.config import (
    ANOMALY_MIN_CATEGORY_TX,
    ANOMALY_Z_THRESHOLD,
    INSTALLMENT_BURDEN_WARNING_PCT,
    REFERENCE_BUDGET_LIMIT,
    format_currency_pt,
)
from src.expenses.ui.insights import HEALTH_RATING_META, MOMENTUM_META, Insight

__all__ = [
    "Insight",
    "anomalies_insight",
    "automated_insights",
    "category_momentum_insight",
    "executive_summary_insight",
    "frequency_change_insight",
    "health_insight",
    "next_month_insight",
    "top_momentum_insight",
]

_R = format_currency_pt
_RATING = {"Excellent": "Excelente", "Good": "Bom", "Fair": "Regular", "At Risk": "Em risco"}
_FACTOR = {
    "installment_burden": "peso das parcelas",
    "anomalies": "transações incomuns",
    "budget_proximity": "proximidade do orçamento do próximo mês",
    "spend_volatility": "volatilidade mês a mês",
}
_VERB = {"rising": "em alta", "falling": "em queda", "stable": "estável"}


def health_insight(df_full: pd.DataFrame) -> Insight | None:
    h = get_financial_health_score(df_full)
    if not h["has_data"]:
        return None
    meta = HEALTH_RATING_META[h["rating"]]
    factor = h["top_factor"]
    return Insight(
        meta["icon"],
        f"Saúde financeira: {h['score']}/100 ({_RATING[h['rating']]})",
        "Nota composta por peso das parcelas, anomalias, proximidade do orçamento futuro e "
        f"volatilidade dos gastos. Ponto mais fraco: **{_FACTOR.get(factor, factor)}** "
        f"({h['components'].get(factor, 0):.0f}/100).",
        meta["severity"],
    )


def next_month_insight(
    df_full: pd.DataFrame, reference_limit: float = REFERENCE_BUDGET_LIMIT
) -> Insight | None:
    m = get_next_month_commitment_metrics(df_full, reference_limit=reference_limit)
    if not m["has_data"]:
        return None
    body = (
        f"**{_R(m['next_month_cost'])}** ({m['pct_of_limit']:.1f}% do limite de "
        f"{_R(reference_limit)}) já estão comprometidos em **{m['num_installments']}** "
        "parcela(s) ativa(s) — "
    )
    diff = _R(abs(m["diff_from_limit"]))
    if m["is_over_limit"]:
        return Insight(
            "⚠️",
            f"Alerta de orçamento do próximo mês ({m['next_month']})",
            body + f"**{diff} acima** do limite.",
            "critical",
        )
    return Insight(
        "🔒",
        f"Orçamento do próximo mês sob controle ({m['next_month']})",
        body + f"**{diff} restantes** dentro do orçamento.",
        "good",
    )


def automated_insights(
    kpis: dict, df_expenses: pd.DataFrame, df_full: pd.DataFrame
) -> list[Insight]:
    """Os cinco insights automáticos da Visão Geral, na ordem de exibição."""
    delta = kpis["mom_delta_pct"]
    if delta > 0:
        mom = Insight(
            "📈",
            "Gastos em alta",
            f"A última fatura está **{delta:.1f}%** maior que a anterior.",
            "warning",
        )
    elif delta < 0:
        mom = Insight(
            "📉",
            "Gastos em queda",
            f"A última fatura caiu **{abs(delta):.1f}%**. Bom trabalho!",
            "good",
        )
    else:
        mom = Insight("⚖️", "Gastos estáveis", "A última fatura é igual à anterior.", "info")

    pct = kpis["installment_pct"]
    if pct > INSTALLMENT_BURDEN_WARNING_PCT:
        inst = Insight(
            "💳",
            "Parcelamento elevado",
            f"**{pct:.1f}%** dos gastos estão presos em parcelas.",
            "warning",
        )
    else:
        inst = Insight(
            "💳",
            "Parcelamento saudável",
            f"Apenas **{pct:.1f}%** dos gastos estão em parcelas.",
            "good",
        )

    anomalies = get_spending_anomalies(
        df_expenses, z_threshold=ANOMALY_Z_THRESHOLD, min_category_tx=ANOMALY_MIN_CATEGORY_TX
    )
    if anomalies.empty:
        anom = Insight(
            "✅",
            "Nenhuma anomalia",
            "Todas as transações seguem o padrão esperado da categoria.",
            "good",
        )
    else:
        anom = Insight(
            "⚠️",
            f"{len(anomalies)} transação(ões) incomum(ns)",
            "Compras bem acima do padrão da categoria. Veja a página **Tendências**.",
            "warning",
        )

    return [
        Insight(
            "🎯",
            "Maior fonte de gastos",
            f"**{kpis['top_cat_name']}** representa **{kpis['top_cat_pct']:.1f}%** do gasto líquido.",
            "info",
        ),
        mom,
        inst,
        anom,
        _pace_insight(df_full),
    ]


def _pace_insight(df_full: pd.DataFrame) -> Insight:
    p = get_month_pace_projection(df_full)
    if not p["has_data"]:
        return Insight(
            "📆", "Ritmo de gastos", "Ainda não há dados para projetar o ritmo do mês.", "info"
        )
    proj = _R(p["projected_total"])
    if p["status"] in ("hot", "cold"):
        hot = p["status"] == "hot"
        return Insight(
            "🔥" if hot else "🧊",
            "Ritmo acelerado" if hot else "Ritmo abaixo do normal",
            f"**{p['current_month']}** deve chegar a **{proj}** "
            f"({p['pace_delta_pct']:+.1f}% vs. a média recente).",
            "warning" if hot else "good",
        )
    return Insight(
        "📆",
        "Ritmo normal",
        f"**{p['current_month']}** segue perto da média recente (projeção de **{proj}**).",
        "info",
    )


def category_momentum_insight(row, category_label: str) -> Insight:
    meta = MOMENTUM_META[row["direction"]]
    return Insight(
        meta["icon"],
        f"{category_label}: {_VERB[row['direction']]}",
        f"Variou **{row['pct_change_over_window']:+.1f}%** nos últimos 3 meses "
        f"(hoje **{_R(row['last_month_value'])}**/mês).",
        meta["severity"],
    )


def top_momentum_insight(momentum: pd.DataFrame) -> Insight:
    rising = momentum[momentum["direction"] == "rising"]
    if rising.empty:
        return Insight(
            "🧭",
            "Momento das categorias",
            "Nenhuma categoria está em alta consistente nos últimos 3 meses.",
            "good",
        )
    top = rising.iloc[0]
    return Insight(
        "📈",
        f"Em alta: {top['category_label']}",
        f"Subiu **{top['pct_change_over_window']:+.1f}%** em 3 meses "
        f"(hoje **{_R(top['last_month_value'])}**/mês).",
        "warning",
    )


def frequency_change_insight(freq: pd.DataFrame) -> Insight:
    top = freq.iloc[0]
    up = top["direction"] == "increased"
    return Insight(
        "🔀" if up else "📉",
        f"Maior mudança: {top['id']}",
        f"Você está comprando {'mais' if up else 'menos'} em **{top['id']}** — "
        f"**{top['recent_monthly_rate']:.1f}x/mês** recentemente contra "
        f"**{top['baseline_monthly_rate']:.1f}x/mês** no histórico ({top['change_pct']:+.0f}%).",
        "warning" if up else "info",
    )


def anomalies_insight(anomalies: pd.DataFrame) -> Insight:
    if anomalies.empty:
        return Insight(
            "✅",
            "Nenhuma anomalia",
            "Todas as transações do período seguem o padrão esperado da categoria.",
            "good",
        )
    return Insight(
        "⚠️",
        f"{len(anomalies)} transação(ões) incomum(ns)",
        "Detectadas no período — bem acima do padrão da categoria.",
        "warning",
    )


def executive_summary_insight(df_exp: pd.DataFrame) -> Insight:
    total = df_exp["cost"].sum()
    monthly = df_exp.groupby("year_month")["cost"].sum()
    ranking = df_exp.groupby("category_label")["cost"].sum().sort_values(ascending=False)
    nf = df_exp[df_exp["category"] == "not_found"]
    nf_val = nf["cost"].sum()
    nf_pct = (nf_val / total * 100) if total > 0 else 0.0

    def pct(v):
        return v / total * 100 if total else 0

    tops = [(ranking.index[i], ranking.iloc[i]) for i in range(min(2, len(ranking)))]
    tops_txt = " e ".join(f"**{n}** ({_R(v)}, {pct(v):.1f}%)" for n, v in tops) or "—"
    return Insight(
        "📌",
        "Resumo executivo",
        f"No período analisado, o gasto acumulado foi **{_R(total)}**. O mês de maior gasto foi "
        f"**{monthly.idxmax() if not df_exp.empty else 'N/D'}** com **{_R(monthly.max() if not df_exp.empty else 0)}**. "
        f"Principais categorias: {tops_txt}. Há **{len(nf)}** transação(ões) sem categoria, "
        f"somando **{_R(nf_val)}** ({nf_pct:.1f}% do total).",
        "warning" if nf_pct > 15 else "info" if nf_pct > 0 else "good",
    )
