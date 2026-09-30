"""Design tokens shared by the Streamlit and Dash dashboards.

The dashboard is deliberately monochrome: one accent hue (plus a lighter tint of it for secondary
marks) over neutral greys. Categories never get their own colour — ranking and position carry the
meaning instead.
"""

ACCENT = "#1F4E79"
ACCENT_LIGHT = "#9DB5CE"
TEXT = "#111827"
MUTED = "#6B7280"
GRID = "#E5E7EB"
BORDER = "#E5E7EB"
BG = "#F7F8FA"
CARD = "#FFFFFF"
FONT = "Inter, -apple-system, 'Segoe UI', Roboto, sans-serif"

PALETTE = (ACCENT, ACCENT_LIGHT)


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
        "xaxis": {"showgrid": False, "zeroline": False, "linecolor": GRID, "title": None},
        "yaxis": {
            "showgrid": True,
            "gridcolor": GRID,
            "zeroline": False,
            "title": None,
            "tickprefix": "R$ ",
            "tickformat": ",.0f",
        },
    }
    layout.update(overrides)
    return layout
