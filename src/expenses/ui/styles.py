import re
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from src.expenses.ui.charts import STATUS_COLORS

_SEVERITY_COLORS = {
    "info": "#00ACC1",
    "good": STATUS_COLORS["good"],
    "warning": STATUS_COLORS["warning"],
    "critical": STATUS_COLORS["critical"],
}

# repo-root/.streamlit/config.toml  (styles.py -> ui -> expenses -> src -> repo root)
_CONFIG_TOML = Path(__file__).resolve().parents[3] / ".streamlit" / "config.toml"


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
            border-left: 3px solid #00ACC1;
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
    st.info/warning/success calls, so narrative insights share one visual language across tabs."""
    color = _SEVERITY_COLORS.get(severity, _SEVERITY_COLORS["info"])
    st.markdown(
        f'<div class="insight-card" style="border-left-color: {color};">'
        f'<div class="insight-card-title">{icon} {title}</div>'
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
        st.caption("✅ Nothing needs your attention right now.")
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
        <div style="padding-bottom: 8px; margin-bottom: 12px; border-bottom: 1px solid color-mix(in srgb, currentColor 15%, transparent);">
            <h2 style="margin: 0; padding: 0; font-size: 1.6rem;">💳 Expenses & Financial Intelligence</h2>
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


def _current_theme_base() -> str:
    try:
        base = st.get_option("theme.base")
    except Exception:  # noqa: BLE001
        base = None
    return base if base in ("light", "dark") else "dark"


def _write_theme_base(base: str) -> None:
    """Rewrites ``base = "..."`` in .streamlit/config.toml (creates the ``[theme]`` block if absent)."""
    try:
        text = _CONFIG_TOML.read_text(encoding="utf-8")
    except OSError:
        return
    if re.search(r'(?m)^\s*base\s*=\s*"[^"]*"', text):
        new_text = re.sub(r'(?m)^(\s*base\s*=\s*)"[^"]*"', rf'\g<1>"{base}"', text, count=1)
    elif re.search(r"(?m)^\[theme\]\s*$", text):
        new_text = re.sub(r"(?m)^(\[theme\]\s*)$", rf'\1\nbase = "{base}"', text, count=1)
    else:
        new_text = text.rstrip() + f'\n\n[theme]\nbase = "{base}"\n'
    if new_text != text:
        try:
            _CONFIG_TOML.write_text(new_text, encoding="utf-8")
        except OSError:
            pass


def render_theme_toggle() -> None:
    """Sidebar button that flips the Streamlit base theme (light <-> dark).

    Streamlit has no public API to hot-swap ``[theme]`` from Python and does not fully repaint a
    base change mid-session, so on click this:

    1. rewrites ``base`` in ``.streamlit/config.toml`` (survives a server restart);
    2. mutates the in-process config via ``streamlit.config`` — what a freshly reloaded session
       reads, since a new session does not re-read the file;
    3. forces a full browser reload so every element (charts included) repaints from the new base.

    The reload starts a fresh session, so sidebar filters and the "Hide amounts" switch reset to
    their defaults. If step 2 is ever rejected at runtime, step 1 still applies on the next restart.
    """
    current = _current_theme_base()
    target = "light" if current == "dark" else "dark"
    label = "☀️ Switch to light" if current == "dark" else "🌙 Switch to dark"
    if st.button(label, width="stretch", key="theme_toggle"):
        _write_theme_base(target)
        try:
            from streamlit import config as _st_config

            _st_config.set_option("theme.base", target)
        except Exception:  # noqa: BLE001
            pass
        components.html("<script>window.parent.location.reload()</script>", height=0)
