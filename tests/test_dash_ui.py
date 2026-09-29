"""Dash frontend: app builds without a DB, every page callback renders through the real Dash
request path, and the cross-filter / pt-BR helpers behave."""

import random

import pandas as pd
import pytest

from src.expenses.config import CATEGORY_CONFIG, format_currency_pt
from src.expenses.dash_ui import create_app, data
from src.expenses.dash_ui.insights_pt import executive_summary_insight, health_insight
from src.expenses.database import _shape_silver_frame
from src.expenses.filters import DEFAULT_FILTERS
from src.expenses.ui.charts import chart_context, money, tr
from src.expenses.ui.figures import build_day_of_week_figure, build_monthly_evolution_figure


def _synthetic_frame() -> pd.DataFrame:
    rng = random.Random(7)
    cats = list(CATEGORY_CONFIG)
    rows = []
    for month in pd.period_range("2025-01", "2026-09", freq="M"):
        invoice = month.to_timestamp() + pd.Timedelta(days=4)
        for _ in range(30):
            total = rng.choice([0, 0, 3, 6])
            rows.append(
                {
                    "date": invoice,
                    "date_buy": invoice - pd.Timedelta(days=rng.randint(3, 28)),
                    "id": f"SHOP {rng.randint(1, 6)}",
                    "cost": round(rng.uniform(15, 400), 2),
                    "installment": rng.randint(1, total) if total else 0,
                    "total_installments": total,
                    "category": rng.choice(cats),
                    "source_debt": "CARD A",
                }
            )
        rows.append({**rows[-1], "id": "PAGAMENTO FATURA", "cost": -2000.0, "category": "food"})
    return _shape_silver_frame(pd.DataFrame(rows))


@pytest.fixture(scope="module")
def df_full():
    return _synthetic_frame()


@pytest.fixture(scope="module")
def app(df_full):
    return create_app(data_loader=lambda: df_full)


FILTERS = {**DEFAULT_FILTERS, "selected_months": [f"2026-{m:02d}" for m in range(4, 10)]}


def _call(app, output_prefix: str, inputs: dict, state: dict | None = None):
    """POSTs to Dash's update endpoint like the browser does; returns the JSON response."""
    client = app.server.test_client()
    dep = next(
        d for d in client.get("/_dash-dependencies").json if d["output"].startswith(output_prefix)
    )
    out = dep["output"]
    ids = out.strip(".").split("...") if out.startswith("..") else [out]
    outputs = [{"id": i.split(".")[0], "property": i.split(".")[1].split("@")[0]} for i in ids]
    payload = {
        "output": out,
        "outputs": outputs if len(outputs) > 1 else outputs[0],
        "inputs": [
            {"id": k.split(".")[0], "property": k.split(".")[1], "value": v}
            for k, v in inputs.items()
        ],
        "state": [
            {"id": k.split(".")[0], "property": k.split(".")[1], "value": v}
            for k, v in (state or {}).items()
        ],
        "changedPropIds": list(inputs)[:1],
    }
    return client.post("/_dash-update-component", json=payload)


COMMON = {"filters.data": FILTERS, "theme.data": "dark", "hide-switch.checked": False}


def test_create_app_without_database():
    from src.expenses.dash_ui.data import configure

    app = create_app(data_loader=lambda: pd.DataFrame())
    assert callable(app.layout)
    configure(lambda: pd.DataFrame())


def test_overview_renders_and_selection_narrows(app):
    base = {
        "filters.data": FILTERS,
        "selection.data": {},
        "theme.data": "dark",
        "hide-switch.checked": False,
        "ov-timeline.value": "year_month",
        "ov-style.value": "stacked",
        "url.pathname": "/",
    }
    ok = _call(app, "..ov-banners.children", base)
    assert ok.status_code == 200 and "Erro" not in ok.text and "ov-kpis" in ok.text
    picked = _call(
        app,
        "..ov-banners.children",
        {**base, "selection.data": {"month": "2026-08", "month_col": "year_month"}},
    )
    assert picked.status_code == 200 and picked.text != ok.text


@pytest.mark.parametrize(
    ("prefix", "extra"),
    [
        ("tr-content.children", {"url.pathname": "/tendencias"}),
        (
            "cat-content.children",
            {"selection.data": {}, "cat-detail.value": "food", "url.pathname": "/categorias"},
        ),
        (
            "cat-content.children",
            {"selection.data": {}, "cat-detail.value": "not_found", "url.pathname": "/categorias"},
        ),
        ("rp-content.children", {"rp-limit.value": 5000, "url.pathname": "/relatorios"}),
    ],
)
def test_pages_render(app, prefix, extra):
    res = _call(app, prefix, {**COMMON, **extra})
    assert res.status_code == 200
    assert "Não foi possível montar" not in res.text


def _pick(_app, trigger: str, click: dict, selection: dict, timeline: str = "year_month"):
    import sys

    module = next(
        m
        for n, m in sys.modules.items()
        if n.endswith("visao_geral") and hasattr(m, "next_selection")
    )
    month = click if trigger == "ov-monthly" else None
    cat = click if trigger == "ov-cats" else None
    return module.next_selection(trigger, month, cat, selection, timeline)


def test_click_month_sets_selection_and_toggles(app):
    click = {"points": [{"x": "2026-07"}]}
    picked = _pick(app, "ov-monthly", click, {})
    assert picked == {"month": "2026-07", "month_col": "year_month"}
    assert _pick(app, "ov-monthly", click, picked) == {}


def test_click_category_maps_label_to_key(app):
    click = {"points": [{"y": CATEGORY_CONFIG["food"]["label"]}]}
    picked = _pick(app, "ov-cats", click, {})
    assert picked == {"category": "food"}
    assert _pick(app, "ov-cats", click, picked) == {}


def test_apply_selection(df_full):
    df = data.apply_selection(df_full, month="2026-03", category="food")
    assert set(df["year_month"]) <= {"2026-03"} and set(df["category"]) <= {"food"}
    assert data.apply_selection(df_full, month="2026-03", month_col="bogus").equals(df_full)


def test_export_csv_payload(df_full):
    payload = data.export_csv(df_full.head(3))
    assert (
        payload["filename"].startswith("relatorio_despesas_")
        and payload["content"].count("\n") == 4
    )


def test_pt_formatting_and_translation(df_full):
    assert format_currency_pt(1234.5) == "R$ 1.234,50"
    assert format_currency_pt(-9.9) == "-R$ 9,90"
    with chart_context(lang="pt"):
        assert money(1234.5) == "R$ 1.234,50"
        assert tr("Month") == "Mês" and tr("Monday") == "Segunda"
    assert money(1234.5) == "R$ 1,234.50" and tr("Month") == "Month"


def test_figures_follow_chart_context(df_full):
    df = df_full[~df_full["is_payment"]]
    with chart_context(theme_base="light", hide_amounts=True, lang="pt"):
        fig = build_monthly_evolution_figure(df)
        dow = build_day_of_week_figure(df)
    assert fig.layout.font.color == "#1F2933" and fig.layout.separators == ",."
    assert not fig.data[-2].text
    assert list(dow.data[0].x)[0] == "Segunda"


def test_pt_insights(df_full):
    assert "Resumo executivo" == executive_summary_insight(df_full[~df_full["is_payment"]]).title
    health = health_insight(df_full)
    assert health is None or "Saúde financeira" in health.title
