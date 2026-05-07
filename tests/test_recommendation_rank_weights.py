import json

from app.chatbot.recommendation_engine import (
    DEFAULT_BASE_RANK_WEIGHTS,
    DEFAULT_PERSONAL_RANK_WEIGHTS,
    RecommendationEngine,
    ShopRecord,
    _build_bm25,
    _tokenize,
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
    assert engine.rank_weight_info["source"] == "artifact.json"
    assert engine.rank_weight_info["active_features"] == ["bm25", "intent", "popularity"]
    assert engine.rank_weight_info["base_weights"]["bm25"] == 0.6


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


def test_rank_weight_artifact_loader_exposes_promotion_metadata(tmp_path):
    artifact = tmp_path / "rank_weight_report.json"
    artifact.write_text(
        json.dumps(
            {
                "status": "ok",
                "top_k": 5,
                "samples": 270,
                "eligible_groups": 9,
                "active_features": ["bm25", "intent", "popularity"],
                "best_weights": {"bm25": 0.6, "intent": 0.4, "popularity": 0.0, "personal": 0.0},
                "baseline_metrics": {"ndcg@5": 0.4644},
                "best_metrics": {"ndcg@5": 0.4942},
                "promotion": {
                    "status": "promoted",
                    "metric": "ndcg@5",
                    "improvement": 0.0298,
                },
            }
        ),
        encoding="utf-8",
    )

    engine = RecommendationEngine()
    assert engine._load_rank_weight_artifact(str(artifact)) is True
    info = engine.rank_weight_info

    assert info["status"] == "artifact"
    assert info["source"] == str(artifact)
    assert info["samples"] == 270
    assert info["eligible_groups"] == 9
    assert info["baseline_metrics"]["ndcg@5"] == 0.4644
    assert info["best_metrics"]["ndcg@5"] == 0.4942
    assert info["promotion"]["status"] == "promoted"
    assert info["promotion"]["improvement"] == 0.0298


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


def test_recommendation_result_exposes_weighted_score_evidence():
    engine = RecommendationEngine()
    engine._shops = [
        ShopRecord(
            shop_id="s1",
            shop_name="성수 파스타 하우스",
            address="서울 성동구 성수동",
            categories=["이탈리안", "파스타"],
            menus=["트러플 파스타"],
            facilities=["예약"],
            awards=[],
        ),
        ShopRecord(
            shop_id="s2",
            shop_name="강남 라멘",
            address="서울 강남구 역삼동",
            categories=["라멘"],
            menus=["돈코츠 라멘"],
            facilities=[],
            awards=[],
        ),
    ]
    engine._bm25 = _build_bm25([_tokenize(shop.document_text()) for shop in engine._shops])
    engine._popularity = {"s1": 0.7, "s2": 0.2}
    engine._query_token_index = {
        "성수": {"s1": 0.8, "s2": 0.1},
        "파스타": {"s1": 0.9},
    }
    engine._query_phrase_index = {"성수 파스타": {"s1": 1.0}}
    engine._loaded = True

    results = engine.recommend(
        "성수 파스타 추천",
        top_k=1,
        profile={"regions": ["성수"], "cuisines": ["파스타"]},
    )

    assert len(results) == 1
    shop = results[0]
    assert shop["shop_id"] == "s1"
    assert set(shop["score_contributions"]) == {"bm25", "intent", "popularity", "personal"}
    assert shop["score_before_adjustments"] == round(sum(shop["score_contributions"].values()), 4)
    assert shop["score"] == shop["score_before_adjustments"]
    assert shop["score_adjustments"] == [
        {
            "type": "region_filter",
            "values": ["성수"],
            "matched": True,
            "factor": 1.0,
        },
        {
            "type": "cuisine_filter",
            "values": ["파스타"],
            "matched": True,
            "factor": 1.0,
        },
    ]
    assert shop["ranking_weight_source"] == "default"
