import json

from scripts import build_recommendation_training_dataset as builder


def _recommendation(shop_id, *, rank=1, bm25=0.8, intent=0.6):
    return {
        "rank": rank,
        "shop_id": shop_id,
        "shop_name": f"shop-{shop_id}",
        "score": 0.7,
        "score_breakdown": {
            "bm25": bm25,
            "intent": intent,
            "popularity": 0.2,
            "personal": 0.0,
        },
        "categories": ["파스타"],
        "menus": ["토마토 파스타", "라구"],
    }


def test_build_samples_for_query_uses_behavior_relevance_labels():
    samples = builder._build_samples_for_query(
        "강남 파스타",
        {"shop-1": 1.0},
        [
            _recommendation("shop-1", rank=1),
            _recommendation("shop-2", rank=2, bm25=0.5, intent=0.1),
        ],
        min_positive_per_query=1,
    )

    assert len(samples) == 2
    assert samples[0]["shop_id"] == "shop-1"
    assert samples[0]["label"] == 1.0
    assert samples[0]["source"] == "behavior_log"
    assert samples[0]["features"]["bm25"] == 0.8
    assert samples[0]["features"]["category_count"] == 1
    assert samples[1]["label"] == 0.0


def test_build_samples_for_query_skips_groups_without_positive_candidate():
    samples = builder._build_samples_for_query(
        "성수 카페",
        {"shop-9": 1.0},
        [_recommendation("shop-1")],
        min_positive_per_query=1,
    )

    assert samples == []


def test_build_recommendation_training_dataset_writes_jsonl(tmp_path, monkeypatch):
    logs_path = tmp_path / "logs.csv"
    output_path = tmp_path / "recommendation_training_samples.jsonl"
    logs_path.write_text(
        "\n".join(
            [
                "event_type,event_timestamp,user_id,session_id,shop_id,search_query,position",
                "click,1,u1,s1,shop-1,강남 파스타,1",
                "view,2,u1,s1,shop-1,,1",
                "click,3,u2,s2,shop-2,강남 파스타,2",
            ]
        ),
        encoding="utf-8",
    )

    class FakeRecommendationEngine:
        def load(self, *, shops_path, logs_path):
            self.shops_path = shops_path
            self.logs_path = logs_path

        def recommend(self, query, top_k, diversify):
            assert query == "강남 파스타"
            assert top_k == 2
            assert diversify is False
            return [
                _recommendation("shop-1", rank=1),
                _recommendation("shop-3", rank=2),
            ]

    monkeypatch.setattr(builder, "recommendation_engine", FakeRecommendationEngine())

    summary = builder.build_recommendation_training_dataset(
        logs_path=logs_path,
        shops_path="shops.csv",
        cache_path="cache.pkl",
        output_path=output_path,
        max_rows=0,
        max_queries=5,
        candidate_k=2,
        min_positive_per_query=1,
    )
    samples = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    ]

    assert summary["queries_considered"] == 1
    assert summary["queries_included"] == 1
    assert summary["samples"] == 2
    assert summary["positive"] == 1
    assert samples[0]["query"] == "강남 파스타"
    assert samples[0]["label"] == 1.0
    assert samples[1]["label"] == 0.0
