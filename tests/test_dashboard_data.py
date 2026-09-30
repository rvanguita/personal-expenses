"""The shared dashboard view model and figures (src/expenses/dashboard)."""

import pandas as pd
import plotly.graph_objects as go

from src.expenses.analytics import calculate_kpis
from src.expenses.config import CATEGORY_COLOR_MAP
from src.expenses.dashboard import (
    PERIOD_LABELS,
    all_figures,
    build_view,
    filter_options,
    kpi_cards,
    month_label,
)
from src.expenses.dashboard.theme import PALETTE
from src.expenses.filters import DEFAULT_FILTERS, apply_filters


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


def test_view_rankings_are_capped_and_sorted(silver_history_df):
    view = build_view(silver_history_df, "All History")
    assert len(view.top_merchants) <= 10
    assert view.top_merchants["total_spent"].is_monotonic_decreasing
    assert view.by_category["cost"].is_monotonic_decreasing
    assert len(view.largest) == 10
    assert view.largest["cost"].is_monotonic_decreasing
    assert "PAGAMENTO FATURA" not in set(view.largest["id"])


def test_view_respects_holder_and_category(silver_history_df):
    view = build_view(silver_history_df, "All History", ["CARDHOLDER_B"], ["food"])
    assert view.by_category["category_label"].tolist() == ["Food & Dining"]
    everything = build_view(silver_history_df, "All History")
    assert view.total < everything.total


def test_commitments_ignore_the_period(silver_history_df):
    short = build_view(silver_history_df, "Last 3 months")
    full = build_view(silver_history_df, "All History")
    pd.testing.assert_frame_equal(short.commitments, full.commitments)
    assert short.next_month_cost == full.next_month_cost


def test_empty_frame_and_empty_selection():
    view = build_view(pd.DataFrame())
    assert view.is_empty
    assert len(kpi_cards(view)) == 4
    for fig in all_figures(view).values():
        assert isinstance(fig, go.Figure)


def test_unmatched_selection_is_empty(silver_history_df):
    view = build_view(silver_history_df, "All History", ["NOBODY"])
    assert view.is_empty
    assert view.last_invoice


def test_filter_options(silver_history_df):
    options = filter_options(silver_history_df)
    assert [k for k, _ in options["periods"]] == list(PERIOD_LABELS)
    assert options["holders"] == ["CARDHOLDER_A", "CARDHOLDER_B"]
    assert ("food", "Food & Dining") in options["categories"]
    assert filter_options(pd.DataFrame())["holders"] == []


def test_kpi_cards_labels(silver_history_df):
    cards = kpi_cards(build_view(silver_history_df))
    assert [c["label"] for c in cards][:2] == ["Gasto no período", "Média mensal"]
    assert all(c["value"].startswith(("R$", "-R$")) for c in cards)


def _trace_colors(trace) -> set[str]:
    marker = getattr(trace.marker, "color", None)
    colors = set(marker) if isinstance(marker, list | tuple) else {marker}
    colors.add(getattr(getattr(trace, "line", None), "color", None))
    return colors - {None}


def test_figures_use_only_the_palette(silver_history_df):
    for fig in all_figures(build_view(silver_history_df, "All History")).values():
        for trace in fig.data:
            assert _trace_colors(trace) <= set(PALETTE), trace.name


def test_category_bars_use_category_colors(silver_history_df):
    figures = all_figures(build_view(silver_history_df, "All History"))
    bar = figures["categories"].data[0]
    assert list(bar.marker.color) == [CATEGORY_COLOR_MAP[label] for label in bar.y]
    assert len(set(figures["merchants"].data[0].marker.color)) > 1


def test_month_label():
    assert month_label("2026-03") == "mar/26"
    assert month_label("bad") == "bad"
