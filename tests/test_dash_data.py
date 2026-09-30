"""Dash dashboard view model and figures (src/expenses/dash_app)."""

import pandas as pd
import plotly.graph_objects as go

from src.expenses.analytics import calculate_kpis
from src.expenses.config import CATEGORY_COLORS
from src.expenses.dash_app.data import (
    PERIOD_LABELS,
    build_view,
    filter_options,
    kpi_cards,
    month_label,
)
from src.expenses.dash_app.figures import (
    category_figure,
    commitments_figure,
    merchants_figure,
    monthly_figure,
)
from src.expenses.dash_app.fmt import LABEL_PT_TO_KEY
from src.expenses.dash_app.theme import PALETTE
from src.expenses.filters import DEFAULT_FILTERS, apply_filters


def _figures(view):
    return [
        monthly_figure(view),
        category_figure(view),
        merchants_figure(view),
        commitments_figure(view),
    ]


def test_view_matches_analytics_kpis(silver_history_df):
    view = build_view(silver_history_df, "Last 6 months")
    months = sorted(silver_history_df["year_month"].unique())[-6:]
    df = apply_filters(silver_history_df, {**DEFAULT_FILTERS, "selected_months": months})
    kpis = calculate_kpis(df, silver_history_df)

    assert not view.is_empty
    assert view.months == months
    assert view.total == kpis["total_spent"]
    assert view.avg_monthly == kpis["avg_monthly_spent"]
    assert view.monthly["year_month"].tolist() == months
    assert view.last_month == months[-1]
    assert view.last_month_delta_pct is not None


def test_rankings_are_capped_sorted_and_exclude_payments(silver_history_df):
    view = build_view(silver_history_df, "All History")
    assert len(view.top_merchants) <= 10
    assert view.top_merchants["total_spent"].is_monotonic_decreasing
    assert view.by_category["cost"].is_monotonic_decreasing
    assert len(view.largest) == 10
    assert view.largest["cost"].is_monotonic_decreasing
    assert "PAGAMENTO FATURA" not in set(view.largest["id"])


def test_holder_and_category_filters(silver_history_df):
    view = build_view(silver_history_df, "All History", ["CARDHOLDER_B"], ["food"])
    assert view.by_category["category"].tolist() == ["food"]
    assert view.total < build_view(silver_history_df, "All History").total


def test_commitments_ignore_the_period(silver_history_df):
    short = build_view(silver_history_df, "Last 3 months")
    full = build_view(silver_history_df, "All History")
    pd.testing.assert_frame_equal(short.commitments, full.commitments)
    assert short.next_month_cost == full.next_month_cost > 0


def test_empty_frame():
    view = build_view(pd.DataFrame())
    assert view.is_empty
    assert len(kpi_cards(view)) == 4
    assert all(isinstance(fig, go.Figure) for fig in _figures(view))


def test_selection_without_rows_is_empty(silver_history_df):
    view = build_view(silver_history_df, "All History", ["NOBODY"])
    assert view.is_empty
    assert view.last_invoice


def test_unknown_period_falls_back_to_default(silver_history_df):
    assert build_view(silver_history_df, "bogus").period_label == PERIOD_LABELS["Last 6 months"]


def test_filter_options(silver_history_df):
    options = filter_options(silver_history_df)
    assert [key for key, _ in options["periods"]] == list(PERIOD_LABELS)
    assert options["holders"] == ["CARDHOLDER_A", "CARDHOLDER_B"]
    assert ("food", "Alimentação") in options["categories"]
    assert filter_options(pd.DataFrame())["holders"] == []


def test_kpi_cards(silver_history_df):
    cards = kpi_cards(build_view(silver_history_df))
    assert [c["label"] for c in cards][:2] == ["Gasto no período", "Média mensal"]
    assert all(c["value"].startswith(("R$", "-R$")) for c in cards)


def _trace_colors(trace) -> set[str]:
    marker = getattr(trace.marker, "color", None)
    colors = set(marker) if isinstance(marker, list | tuple) else {marker}
    colors.add(getattr(getattr(trace, "line", None), "color", None))
    return colors - {None}


def test_figures_use_only_the_palette(silver_history_df):
    for fig in _figures(build_view(silver_history_df, "All History")):
        for trace in fig.data:
            assert _trace_colors(trace) <= set(PALETTE), trace.name


def test_category_bars_use_category_colors(silver_history_df):
    view = build_view(silver_history_df, "All History")
    bar = category_figure(view).data[0]
    assert list(bar.marker.color) == [CATEGORY_COLORS[LABEL_PT_TO_KEY[label]] for label in bar.y]
    assert len(set(merchants_figure(view).data[0].marker.color)) > 1


def test_month_label():
    assert month_label("2026-03") == "mar/26"
    assert month_label("bad") == "bad"
