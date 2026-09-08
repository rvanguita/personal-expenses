import pandas as pd

from src.expenses.ai_categorizer import match_merchants_with_history


def test_match_merchants_with_history_dictionary():
    # Test dictionary-based keyword matching with deliberately fictional merchants.
    df_sample = pd.DataFrame(
        [
            {"id": "EXAMPLE RESTAURANTE 123", "cost": 35.0},
            {"id": "SAMPLE RETAIL 456", "cost": 250.0},
            {"id": "UNKNOWN ENTITY 999", "cost": 100.0},
        ]
    )
    df_matched, df_unmatched = match_merchants_with_history(df_sample, engine=None)

    assert not df_matched.empty
    assert len(df_matched) == 2
    assert "EXAMPLE RESTAURANTE 123" in df_matched["id"].values
    assert df_matched[df_matched["id"] == "EXAMPLE RESTAURANTE 123"]["category"].iloc[0] == "food"
    assert "SAMPLE RETAIL 456" in df_matched["id"].values
    assert df_matched[df_matched["id"] == "SAMPLE RETAIL 456"]["category"].iloc[0] == "shopping"

    assert not df_unmatched.empty
    assert len(df_unmatched) == 1
    assert "UNKNOWN ENTITY 999" in df_unmatched["id"].values


def test_batch_gemini_categorize_unmatched_empty():
    from src.expenses.ai_categorizer import batch_gemini_categorize_unmatched

    df_empty = pd.DataFrame(columns=["id"])
    res = batch_gemini_categorize_unmatched(df_empty, batch_size=25)
    assert res.empty


def test_batch_gemini_categorize_unmatched_callback(monkeypatch):
    from src.expenses.ai_categorizer import batch_gemini_categorize_unmatched

    # Mock single batch function
    def mock_gemini_cat(df):
        return pd.DataFrame(
            [
                {
                    "id": row["id"],
                    "category": "food",
                    "motivation": "mock",
                    "categorized_by": "gemini_ai",
                }
                for _, row in df.iterrows()
            ]
        )

    monkeypatch.setattr("src.expenses.ai_categorizer.gemini_categorize_unmatched", mock_gemini_cat)

    df_many = pd.DataFrame([{"id": f"MERCHANT_{i}"} for i in range(60)])
    callbacks_received = []

    def on_progress(batch_num, total_batches, chunk_len, total_count):
        callbacks_received.append((batch_num, total_batches, chunk_len, total_count))

    res = batch_gemini_categorize_unmatched(df_many, batch_size=25, progress_callback=on_progress)
    assert len(res) == 60
    assert callbacks_received[0] == (1, 3, 25, 60)
    assert callbacks_received[1] == (2, 3, 25, 60)
    assert callbacks_received[2] == (3, 3, 10, 60)


def test_repopulate_silver_layer_empty(monkeypatch):
    from src.expenses.ai_categorizer import repopulate_silver_layer

    monkeypatch.setattr("src.expenses.ai_categorizer.load_bronze_data", lambda: pd.DataFrame())
    res = repopulate_silver_layer(batch_size=25)
    assert res["status"] == "empty"
    assert res["silver_count"] == 0


def test_save_dataframe_replace_noop():
    from src.expenses.database import save_dataframe_replace

    # Engine is None should safely return without exception
    save_dataframe_replace(pd.DataFrame(), engine=None)
    save_dataframe_replace(pd.DataFrame([{"id": "TEST"}]), engine=None)
