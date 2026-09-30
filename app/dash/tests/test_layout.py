"""Static structure and shared components in expenses_dash.layout."""

import pandas as pd
from dash import dcc, html

from expenses_dash.data import filter_options
from expenses_dash.layout import (
    FIGURE_IDS,
    TABS,
    _category_tab,
    _cell,
    _filter,
    _filters,
    _overview,
    _reports_tab,
    build_layout,
    card,
    empty,
    graph,
    kpi_card,
    kpi_row,
    purchases_table,
    row,
    table,
)

CARD = {"label": "Spend", "value": "R$ 10.00", "note": "▲ 5.0%", "help": "help text", "tone": "bad"}


def test_card_and_note():
    c = card("Title", html.P("body"), note="note")
    assert c.className == "pe-card"
    title, note, body = c.children
    assert (title.children, note.children, body.children) == ("Title", "note", "body")
    assert len(card("Title only").children) == 1


def test_graph_with_and_without_id():
    with_id = graph(None, "fig-x")
    assert isinstance(with_id, dcc.Graph) and with_id.id == "fig-x"
    assert with_id.config == {"displayModeBar": False}
    assert getattr(graph({"data": []}), "id", None) is None


def test_kpi_card_tone_and_help():
    c = kpi_card(CARD)
    assert c.title == "help text"
    note = c.children[2]
    assert note.children == "▲ 5.0%" and "pe-tone-bad" in note.className
    no_tone = {k: v for k, v in CARD.items() if k != "tone"}
    assert "pe-tone-neutral" in kpi_card(no_tone).children[2].className


def test_kpi_row_row_and_empty():
    assert len(kpi_row([CARD, CARD]).children) == 2
    assert row(html.Div(), html.Div()).className == "pe-grid-2"
    assert empty("nada").children == "nada"


def test_cell_kinds():
    record = {"category": "food"}
    assert _cell(1234.5, "money", record).children == "R$ 1,234.50"
    assert _cell(pd.Timestamp("2026-03-01"), "date", record).children == "2026-03-01"
    assert _cell(pd.NaT, "date", record).children == "—"
    assert _cell("2026-03", "month", record).children == "Mar 26"
    assert _cell(12.34, "pct", record).children == "+12.3%"
    assert _cell(1.26, "rate", record).children == "1.3"
    assert _cell(1234, "int", record).children == "1,234"
    dot, label = _cell("Food & Dining", "category", record).children
    assert label == "Food & Dining" and dot.style["backgroundColor"] == "#FF9800"
    assert _cell("texto", "text", record).children == "texto"


def test_table_headers_rows_and_limit():
    df = pd.DataFrame({"a": ["x", "y", "z"], "v": [1.0, 2.0, 3.0]})
    t = table(df, [("A", "a", "text"), ("Valor", "v", "money")], max_rows=2)
    head, body = t.children.children
    assert [th.children for th in head.children.children] == ["A", "Valor"]
    assert head.children.children[1].className == "pe-num"
    assert len(body.children) == 2
    assert table(df.iloc[0:0], [("A", "a", "text")]).children == "Nothing to show."


def test_purchases_table():
    df = pd.DataFrame(
        {
            "date_buy": [pd.Timestamp("2026-01-02")],
            "id": ["LOJA"],
            "category": ["food"],
            "category_label": ["Food & Dining"],
            "cost": [10.0],
        }
    )
    body = purchases_table(df).children.children[1]
    assert len(body.children) == 1


def test_filter_and_filters(silver_history_df, ids):
    f = _filter("Label", dcc.Dropdown(id="dd"))
    assert f.children[0].htmlFor == "dd"
    assert ids(_filters(filter_options(silver_history_df))) == {
        "f-period",
        "f-holders",
        "f-categories",
    }


def test_tab_bodies(ids):
    assert {"kpis", "largest", *(f"fig-{n}" for n in FIGURE_IDS)} <= ids(_overview())
    assert ids(_category_tab()) == {"f-category-detail", "category-content"}
    assert ids(_reports_tab()) == {"reports-content", "btn-csv", "download-csv"}


def test_build_layout(silver_history_df, ids):
    layout = build_layout(filter_options(silver_history_df))
    tabs = next(c for c in layout.children if isinstance(c, dcc.Tabs))
    assert [t.value for t in tabs.children] == [value for value, _ in TABS]
    assert {"subtitle", "tabs", "habits-content", "watchlist-content"} <= ids(layout)
