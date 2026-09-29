import dash
import dash_mantine_components as dmc
import pandas as pd
from dash import Input, Output, State, callback, html
from dash.exceptions import PreventUpdate

from src.expenses.analytics import get_category_momentum
from src.expenses.config import CATEGORY_CONFIG, DAY_OF_WEEK_LABELS_PT, format_currency_pt
from src.expenses.dash_ui import data
from src.expenses.dash_ui.insights_pt import category_momentum_insight
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
from src.expenses.ui.charts import build_ranked_bar_chart
from src.expenses.ui.figures import build_category_monthly_figure, build_day_of_week_figure

dash.register_page(__name__, path="/categorias", name="Categorias", title="Categorias")

R = format_currency_pt
DOW = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

layout = dmc.Stack(
    [
        dmc.Select(
            id="cat-detail",
            label="Categoria para análise detalhada",
            data=[],
            allowDeselect=False,
            searchable=True,
            w={"base": "100%", "sm": 360},
        ),
        html.Div(id="cat-content"),
    ],
    gap="md",
)


def _options(df: pd.DataFrame) -> list[dict]:
    cats = [c for c in sorted(df["category"].unique()) if c in CATEGORY_CONFIG]
    if "not_found" in cats:
        cats.remove("not_found")
        cats.append("not_found")
    return [
        {"value": c, "label": f"{CATEGORY_CONFIG[c]['icon']} {CATEGORY_CONFIG[c]['label']}"}
        for c in cats
    ]


def _uncategorized(df: pd.DataFrame):
    nf = df[(df["category"] == "not_found") & (df["cost"] > 0)]
    if nf.empty:
        return None
    total_exp = float(df[df["cost"] > 0]["cost"].sum())
    total = float(nf["cost"].sum())
    top = (
        nf.groupby("id")["cost"]
        .sum()
        .reset_index()
        .sort_values("cost", ascending=False)
        .head(5)
        .rename(columns={"id": "Estabelecimento", "cost": "Total"})
    )
    latest = nf.sort_values("date_buy", ascending=False).head(5)
    latest_t = pd.DataFrame(
        {
            "Data da compra": pd.to_datetime(latest["date_buy"]),
            "Estabelecimento": latest["id"],
            "Valor": latest["cost"].astype(float),
        }
    )
    return panel(
        f"❓ Sem categoria: {R(total)} ({len(nf)} transações, {total / total_exp * 100 if total_exp else 0:.1f}% do total)",
        dmc.Text(
            "Classifique-as com o Gemini na aba de categorização do app Streamlit.",
            size="xs",
            c="dimmed",
        ),
        two_col(
            html.Div(
                [
                    dmc.Text("Maiores estabelecimentos sem categoria", fw=600, size="sm"),
                    data_table(top, money=("Total",), page_size=5),
                ]
            ),
            html.Div(
                [
                    dmc.Text("Últimos itens sem categoria", fw=600, size="sm"),
                    data_table(latest_t, money=("Valor",), page_size=5),
                ]
            ),
            ratio="1fr 1fr",
        ),
    )


def _dow_table(df_cat: pd.DataFrame, total: float) -> pd.DataFrame:
    agg = (
        df_cat.assign(day=df_cat["date_buy"].dt.day_name())
        .groupby("day")
        .agg(total_sum=("cost", "sum"), n=("cost", "count"))
        .reindex(DOW)
        .fillna(0.0)
        .reset_index()
    )
    agg["avg"] = (agg["total_sum"] / agg["n"].where(agg["n"] > 0)).fillna(0.0)
    agg["share"] = agg["total_sum"] / total * 100 if total > 0 else 0.0
    return agg


@callback(
    Output("cat-detail", "data"),
    Output("cat-detail", "value"),
    Input("filters", "data"),
    State("cat-detail", "value"),
    State("selection", "data"),
    Input("url", "pathname"),
)
def update_selector(filters, current, selection, pathname):
    if pathname != "/categorias" or not filters:
        raise PreventUpdate
    _, df = data.get_frames(filters)
    if df.empty:
        return [], None
    options = _options(df)
    values = [o["value"] for o in options]
    preferred = (selection or {}).get("category")
    value = (
        current
        if current in values
        else preferred
        if preferred in values
        else (values[0] if values else None)
    )
    return options, value


@callback(
    Output("cat-content", "children"),
    Input("filters", "data"),
    Input("selection", "data"),
    Input("theme", "data"),
    Input("hide-switch", "checked"),
    Input("cat-detail", "value"),
    Input("url", "pathname"),
)
@safe_render()
def render(filters, selection, theme, hide, category, pathname):
    if pathname != "/categorias":
        raise PreventUpdate
    selection = selection or {}
    _, df = data.get_frames(filters)
    df = data.apply_selection(
        df, selection.get("month"), month_col=selection.get("month_col", "year_month")
    )
    if df.empty:
        return empty("Nenhuma transação para analisar.")

    blocks = [section("🔍 Análise por categoria"), _uncategorized(df)]
    if category not in CATEGORY_CONFIG or category not in set(df["category"]):
        return dmc.Stack([*blocks, empty("Selecione uma categoria para ver o detalhe.")], gap="md")

    meta = CATEGORY_CONFIG[category]
    d = df[(df["category"] == category) & (df["cost"] > 0)].copy()
    total, count = float(d["cost"].sum()), len(d)
    global_exp = float(df[df["cost"] > 0]["cost"].sum())

    mom = get_category_momentum(df, window=3)
    mom_row = mom[mom["category"] == category]
    if not mom_row.empty:
        blocks.append(insight_card(category_momentum_insight(mom_row.iloc[0], meta["label"])))

    peak_date, peak_val = "N/D", 0.0
    if not d.empty:
        daily = d.groupby(d["date_buy"].dt.date)["cost"].sum()
        peak_date = pd.to_datetime(daily.idxmax()).strftime("%d/%m/%Y")
        peak_val = float(daily.max())
    dow = _dow_table(d, total)
    top_dow = dow.loc[dow["total_sum"].idxmax()]
    has_dow = top_dow["total_sum"] > 0

    blocks.append(
        kpi_grid(
            kpi("Total da categoria", R(total)),
            kpi("Transações", f"{count:,}".replace(",", ".")),
            kpi("Ticket médio", R(total / count if count else 0.0)),
            kpi("Participação", f"{total / global_exp * 100 if global_exp else 0:.1f}%"),
            kpi("Dia de pico (data)", peak_date, delta=R(peak_val)),
            kpi(
                "Dia da semana de pico",
                DAY_OF_WEEK_LABELS_PT[top_dow["day"]] if has_dow else "N/D",
                delta=R(float(top_dow["total_sum"])) if has_dow else None,
            ),
            cols=3,
        )
    )

    merchants = (
        d.groupby("id")["cost"].sum().reset_index().sort_values("cost", ascending=False).head(7)
    )
    with render_ctx(theme, hide):
        history = dynamic_graph(build_category_monthly_figure(d, meta["label"], meta["color"]))
        top_m = dynamic_graph(
            build_ranked_bar_chart(merchants, "id", "cost", height=340)
            if not merchants.empty
            else None
        )
        dow_fig = dynamic_graph(build_day_of_week_figure(d, height=340, headroom=1.25))
    blocks += [
        two_col(
            panel(f"Histórico mensal: {meta['label']}", history),
            panel("Principais estabelecimentos", top_m),
        ),
        section(f"📅 Gasto por dia da semana: {meta['label']}"),
        two_col(
            panel("Gráfico", dow_fig),
            panel(
                "Detalhamento",
                data_table(
                    pd.DataFrame(
                        {
                            "Dia": dow["day"].map(lambda x: DAY_OF_WEEK_LABELS_PT[x]),
                            "Total": dow["total_sum"].astype(float),
                            "Tx": dow["n"].astype(int),
                            "Ticket": dow["avg"].astype(float),
                            "% do total": dow["share"].astype(float),
                        }
                    ),
                    money=("Total", "Ticket"),
                    integer=("Tx",),
                    decimal=("% do total",),
                    page_size=7,
                ),
            ),
        ),
    ]
    top_tx = d.sort_values("cost", ascending=False).head(15)
    blocks += [
        section("📋 Maiores transações da categoria"),
        panel(
            None,
            data_table(
                pd.DataFrame(
                    {
                        "Data da fatura": pd.to_datetime(top_tx["date"]),
                        "Data da compra": pd.to_datetime(top_tx["date_buy"]),
                        "Estabelecimento": top_tx["id"],
                        "Valor": top_tx["cost"].astype(float),
                        "Parcelas": [
                            f"{int(i)}/{int(t)}" if t > 1 else "À vista"
                            for i, t in zip(
                                top_tx["installment"], top_tx["total_installments"], strict=True
                            )
                        ],
                    }
                ),
                money=("Valor",),
            ),
        ),
    ]
    return dmc.Stack([b for b in blocks if b is not None], gap="md")
