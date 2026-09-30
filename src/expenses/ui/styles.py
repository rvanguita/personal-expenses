import re

import streamlit as st

from src.expenses.ui.charts import STATUS_COLORS

_SEVERITY_COLORS = {
    "info": "#4C9BE8",
    "good": STATUS_COLORS["good"],
    "warning": STATUS_COLORS["warning"],
    "critical": STATUS_COLORS["critical"],
}


def apply_custom_styles():
    """Injects insight-card CSS derived from ``currentColor`` (the active theme's text color), so it
    tracks whichever ``[theme] base`` is active (light or dark) without any Python branching.
    Streamlit does not expose its theme as CSS variables, so ``var(--...)`` would only ever hit
    the fallback."""
    st.markdown(
        """
        <style>
        .insight-card {
            background-color: color-mix(in srgb, currentColor 5%, transparent);
            border: 1px solid color-mix(in srgb, currentColor 14%, transparent);
            border-left: 3px solid #4C9BE8;
            border-radius: 8px;
            padding: 10px 14px;
            margin-bottom: 8px;
            height: 100%;
        }
        .insight-card-title {
            font-size: 0.9rem;
            font-weight: 600;
            margin-bottom: 2px;
        }
        .insight-card-message {
            font-size: 0.85rem;
            opacity: 0.75;
            line-height: 1.45;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _inline_markdown_to_html(text: str) -> str:
    """The card body is raw HTML (markdown isn't parsed inside it): render ``**bold**`` and show
    currency ``$`` literally (``format_currency_md`` pre-escapes it as ``\\$``)."""
    text = text.replace("\\$", "&#36;").replace("$", "&#36;")
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def render_insight_card(icon: str, title: str, message: str, severity: str = "info") -> None:
    """Renders a severity-colored insight card (info/good/warning/critical) in place of ad hoc
    st.info/warning/success calls, so narrative insights share one visual language across tabs.
    The severity color carries the signal; ``icon`` is accepted but not drawn, to keep cards quiet."""
    color = _SEVERITY_COLORS.get(severity, _SEVERITY_COLORS["info"])
    st.markdown(
        f'<div class="insight-card" style="border-left-color: {color};">'
        f'<div class="insight-card-title">{title}</div>'
        f'<div class="insight-card-message">{_inline_markdown_to_html(message)}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def render_insight(insight) -> None:
    """Renders an ``ui.insights.Insight`` as an insight card (no-op for ``None``)."""
    if insight is not None:
        render_insight_card(insight.icon, insight.title, insight.message, severity=insight.severity)


def render_attention(insights: list) -> None:
    """'Needs attention' strip: one compact card per actionable insight, or a quiet all-clear."""
    if not insights:
        st.caption("Nothing needs your attention right now.")
        return
    for col, insight in zip(st.columns(len(insights)), insights, strict=True):
        with col:
            render_insight(insight)


def section(title: str, caption: str | None = None) -> None:
    """Uniform section heading used by every analytic tab."""
    st.markdown(f"##### {title}")
    if caption:
        st.caption(caption)


def render_header():
    """Renders the compact page header."""
    st.markdown(
        """
        <div style="padding-bottom: 10px; margin-bottom: 14px; border-bottom: 1px solid color-mix(in srgb, currentColor 12%, transparent);">
            <h2 style="margin: 0; padding: 0; font-size: 1.5rem; font-weight: 650;">Expenses</h2>
            <p style="margin: 2px 0 0 0; opacity: 0.6; font-size: 0.9rem;">
                Credit card spending, trends and commitments
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_amount_visibility_css(hidden: bool) -> None:
    """Blurs on-screen monetary figures when ``hidden`` is set; hovering an element reveals it.
    Toggled globally from the sidebar so no individual call site needs to change. Covers KPI
    values/deltas, insight-card text, anything tagged ``.hide-amount``, and — since amounts also
    live inside Plotly figures (axis ticks, bar labels, total lines) and dataframe currency
    columns — whole charts and tables too (``stDataEditor`` is left out so editing stays usable)."""
    if not hidden:
        return
    st.markdown(
        """
        <style>
        [data-testid="stMetricValue"],
        [data-testid="stMetricDelta"],
        [data-testid="stPlotlyChart"],
        [data-testid="stDataFrame"],
        [data-testid="stTable"],
        .insight-card-message,
        .hide-amount {
            filter: blur(6px);
            transition: filter 0.15s ease;
        }
        [data-testid="stMetricValue"]:hover,
        [data-testid="stMetricDelta"]:hover,
        [data-testid="stPlotlyChart"]:hover,
        [data-testid="stDataFrame"]:hover,
        [data-testid="stTable"]:hover,
        .insight-card-message:hover,
        .hide-amount:hover {
            filter: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
