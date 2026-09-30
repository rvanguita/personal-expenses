"""Dark-theme design tokens for the Dash dashboard (mirrored as CSS variables in
`assets/dashboard.css`).

Category marks take their colour from `config.CATEGORY_CONFIG`; the non-categorical series
(monthly total, 3-month average, future installments) use the three series colours below.
"""

from src.expenses.config import CATEGORY_COLOR_MAP, CATEGORY_COLORS

BG = "#0F1117"
CARD = "#161A23"
BORDER = "#262B36"
TEXT = "#E5E7EB"
MUTED = "#9CA3AF"
FONT = "Inter, -apple-system, 'Segoe UI', Roboto, sans-serif"

ACCENT = "#4C9BE8"  # monthly total, KPI values
AVERAGE = "#F5B942"  # 3-month moving average
COMMITMENT = "#2BB5A0"  # future installments

FALLBACK = CATEGORY_COLORS["not_found"]
PALETTE = (ACCENT, AVERAGE, COMMITMENT, *CATEGORY_COLORS.values())


def category_color(key: str) -> str:
    """Colour for a category key (e.g. ``food``)."""
    return CATEGORY_COLORS.get(key, FALLBACK)


def category_label_color(label: str) -> str:
    """Colour for a category display label (e.g. ``Food & Dining``)."""
    return CATEGORY_COLOR_MAP.get(label, FALLBACK)


def plotly_layout(height: int = 320, **overrides) -> dict:
    """Base Plotly layout: transparent background, value-axis grid only, no legend."""
    layout = {
        "height": height,
        "margin": {"l": 8, "r": 8, "t": 8, "b": 8},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": FONT, "size": 12, "color": MUTED},
        "showlegend": False,
        "hoverlabel": {"bgcolor": CARD, "bordercolor": BORDER, "font": {"color": TEXT}},
        "separators": ".,",
        "bargap": 0.35,
        "xaxis": {"showgrid": False, "zeroline": False, "linecolor": BORDER, "title": None},
        "yaxis": {
            "showgrid": True,
            "gridcolor": BORDER,
            "zeroline": False,
            "title": None,
            "tickprefix": "R$ ",
            "tickformat": ",.0f",
        },
    }
    layout.update(overrides)
    return layout
