import json

from app.chatbot.recommendation_engine import (
    DEFAULT_BASE_RANK_WEIGHTS,
    DEFAULT_PERSONAL_RANK_WEIGHTS,
    RecommendationEngine,
)


def test_rank_weight_artifact_preserves_personal_budget_without_personal_feature():
    engine = RecommendationEngine()

    applied = engine._apply_rank_weights(
        {"bm25": 0.6, "intent": 0.4, "popularity": 0.0, "personal": 0.0},
        active_features=["bm25", "intent", "popularity"],
        source="artifact.json",
    )

    assert applied is True
    assert engine._base_rank_weights == {
        "bm25": 0.6,
        "intent": 0.4,
        "popularity": 0.0,
        "personal": 0.0,
    }
    assert engine._personal_rank_weights == {
        "bm25": 0.48,
        "intent": 0.32,
        "popularity": 0.0,
        "personal": 0.2,
    }
    assert engine.rank_weight_source == "artifact.json"


def test_rank_weight_artifact_uses_personal_weight_when_feature_is_active():
    engine = RecommendationEngine()

    applied = engine._apply_rank_weights(
        {"bm25": 0.3, "intent": 0.2, "popularity": 0.1, "personal": 0.4},
        active_features=["bm25", "intent", "popularity", "personal"],
        source="feedback-artifact.json",
    )

    assert applied is True
    assert engine._base_rank_weights == {
        "bm25": 0.5,
        "intent": 0.333333,
        "popularity": 0.166667,
        "personal": 0.0,
    }
    assert engine._personal_rank_weights == {
        "bm25": 0.3,
        "intent": 0.2,
        "popularity": 0.1,
        "personal": 0.4,
    }


def test_rank_weight_artifact_loader_falls_back_for_inactive_report(tmp_path):
    artifact = tmp_path / "rank_weight_report.json"
    artifact.write_text(
        json.dumps(
            {
                "status": "ok",
                "active_features": ["bm25", "intent"],
                "best_weights": {"bm25": 0.7, "intent": 0.3},
            }
        ),
        encoding="utf-8",
    )
    engine = RecommendationEngine()
    assert engine._load_rank_weight_artifact(str(artifact)) is True
    assert engine.rank_weight_source == str(artifact)

    artifact.write_text(
        json.dumps({"status": "insufficient_data", "best_weights": None}),
        encoding="utf-8",
    )

    assert engine._load_rank_weight_artifact(str(artifact)) is False
    assert engine._base_rank_weights == DEFAULT_BASE_RANK_WEIGHTS
    assert engine._personal_rank_weights == DEFAULT_PERSONAL_RANK_WEIGHTS
    assert engine.rank_weight_source == "default"


def test_recommendation_engine_load_handles_missing_csvs(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_CACHE_PATH", str(tmp_path / "missing_cache.pkl"))
    monkeypatch.setenv("CHATBOT_RANK_WEIGHT_PATH", str(tmp_path / "missing_rank_weights.json"))
    engine = RecommendationEngine()

    engine.load(
        shops_path=str(tmp_path / "missing_shops.csv"),
        logs_path=str(tmp_path / "missing_logs.csv"),
    )

    assert engine.is_ready() is False
    assert engine.recommend("강남 파스타") == []
