"""Minimal CSS for the Streamlit dashboard, built from the shared `dashboard.theme` tokens."""

import streamlit as st

from src.expenses.dashboard.theme import ACCENT, BORDER, CARD, FONT, MUTED, TEXT

_CSS = f"""
<style>
html, body, [class*="css"] {{ font-family: {FONT}; }}
#MainMenu, footer, [data-testid="stToolbarActions"] {{ visibility: hidden; }}
.block-container {{ padding-top: 4rem; max-width: 1280px; }}
h1, h2, h3 {{ color: {TEXT}; letter-spacing: -0.01em; }}
.pe-title {{ font-size: 1.6rem; font-weight: 650; color: {TEXT}; margin: 0; }}
.pe-subtitle {{ color: {MUTED}; font-size: 0.9rem; margin: 0.15rem 0 1.25rem; }}
.pe-section {{
    font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;
    color: {MUTED}; margin: 0 0 0.5rem;
}}
[data-testid="stMetric"] {{ background: {CARD}; border-color: {BORDER} !important; }}
[data-testid="stMetricLabel"] p {{ color: {MUTED}; font-size: 0.8rem; font-weight: 600; }}
[data-testid="stMetricValue"] {{ color: {ACCENT}; font-weight: 650; font-size: 1.75rem; }}
[data-testid="stMetricDelta"] {{ color: {MUTED}; background: none; padding: 0; }}
[data-testid="stVerticalBlockBorderWrapper"] {{ background: {CARD}; }}
</style>
"""


def apply_style() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def header(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="pe-title">{title}</div><div class="pe-subtitle">{subtitle}</div>',
        unsafe_allow_html=True,
    )


def section(title: str) -> None:
    st.markdown(f'<div class="pe-section">{title}</div>', unsafe_allow_html=True)
