from app.streamlit.ui import insights
from app.streamlit.ui.insights import Insight, attention_insights, uncategorized_insight
from src.expenses.analytics import calculate_kpis


def _kpis(installment_pct: float) -> dict:
    return {"installment_pct": installment_pct}


def test_attention_only_actionable_critical_first_and_capped(monkeypatch, silver_history_df):
    monkeypatch.setattr(
        insights, "next_month_insight", lambda *_a, **_k: Insight("!", "over", "m", "critical")
    )
    monkeypatch.setattr(insights, "_pace_insight", lambda *_a: Insight("!", "pace", "m", "warning"))
    monkeypatch.setattr(
        insights, "_anomaly_summary_insight", lambda *_a: Insight("!", "anom", "m", "warning")
    )
    monkeypatch.setattr(insights, "uncategorized_insight", lambda *_a: None)
    df = silver_history_df[~silver_history_df["is_payment"]]

    result = attention_insights(_kpis(90.0), df, silver_history_df, limit=3)

    assert [i.severity for i in result] == ["critical", "warning", "warning"]
    assert result[0].title == "over"


def test_attention_drops_good_and_info(monkeypatch, silver_history_df):
    for name in ("_pace_insight", "_anomaly_summary_insight"):
        monkeypatch.setattr(insights, name, lambda *_a: Insight("", "ok", "", "good"))
    monkeypatch.setattr(insights, "next_month_insight", lambda *_a, **_k: None)
    monkeypatch.setattr(insights, "uncategorized_insight", lambda *_a: None)
    df = silver_history_df[~silver_history_df["is_payment"]]

    assert attention_insights(_kpis(1.0), df, silver_history_df) == []


def test_attention_runs_on_real_frame(silver_history_df):
    df = silver_history_df[~silver_history_df["is_payment"]]
    kpis = calculate_kpis(silver_history_df, silver_history_df)
    result = attention_insights(kpis, df, silver_history_df)
    assert len(result) <= 3
    assert all(i.severity in ("critical", "warning") for i in result)


def test_uncategorized_insight_threshold(sample_expenses_df):
    df = sample_expenses_df.copy()
    assert uncategorized_insight(df) is None
    df.loc[df["id"] == "DEMO STORE", "category"] = "not_found"  # 400 of 830.50 = 48%
    insight = uncategorized_insight(df)
    assert insight is not None and insight.severity == "warning"
    assert "48.2%" in insight.message
