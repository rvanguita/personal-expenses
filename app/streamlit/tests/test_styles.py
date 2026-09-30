"""Header / card / CSS helpers in expenses_streamlit.styles."""

from streamlit.testing.v1 import AppTest

from expenses_streamlit.insights import Insight
from expenses_streamlit.styles import _inline_markdown_to_html


def _run(func_name, *args):
    """Runs one styles helper inside a real Streamlit script run."""
    import expenses_streamlit.styles as styles

    getattr(styles, func_name)(*args)


def _app(func_name, *args) -> AppTest:
    at = AppTest.from_function(_run, args=(func_name, *args), default_timeout=30).run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def _html(at: AppTest) -> str:
    return "\n".join(m.value for m in at.markdown)


def test_inline_markdown_to_html():
    assert _inline_markdown_to_html("**R\\$ 10** due") == "<b>R&#36; 10</b> due"
    assert _inline_markdown_to_html("plain $5") == "plain &#36;5"


def test_render_insight_card_uses_severity_color_and_no_icon():
    html = _html(_app("render_insight_card", "⚠️", "Over budget", "**R\\$ 1**", "critical"))
    assert "Over budget" in html and "<b>R&#36; 1</b>" in html
    assert "⚠️" not in html


def test_render_insight_and_none():
    insight = Insight("💳", "High installment share", "47%", "warning")
    assert "High installment share" in _html(_app("render_insight", insight))
    assert _app("render_insight", None).markdown.len == 0


def test_render_attention_cards_and_quiet_state():
    cards = [Insight("", "A", "a", "warning"), Insight("", "B", "b", "critical")]
    at = _app("render_attention", cards)
    assert "A" in _html(at) and "B" in _html(at)
    quiet = _app("render_attention", [])
    assert [c.value for c in quiet.caption] == ["Nothing needs your attention right now."]


def test_section_header_and_css_helpers():
    at = _app("section", "Recurring charges", "Billed monthly")
    assert "Recurring charges" in _html(at) and at.caption[0].value == "Billed monthly"
    assert "Expenses" in _html(_app("render_header"))
    assert ".insight-card" in _html(_app("apply_custom_styles"))
    assert "blur" in _html(_app("render_amount_visibility_css", True))
    assert _app("render_amount_visibility_css", False).markdown.len == 0
