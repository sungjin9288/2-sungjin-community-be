import json

from scripts.export_chatbot_learning_dataset import export_training_dataset
from scripts.evaluate_recommendation import _mrr, _ndcg, _percentile
from scripts.tune_chatbot_rank_weights import tune_rank_weights


def test_export_chatbot_learning_dataset_links_feedback_to_last_recommendation(tmp_path):
    input_path = tmp_path / "learning.jsonl"
    output_path = tmp_path / "training.jsonl"
    events = [
        {
            "event_type": "chat",
            "session_id": "session-a",
            "message": "강남 파스타 추천해줘",
            "recommendations": [
                {
                    "shop_id": "shop-1",
                    "shop_name": "파스타집",
                    "rank": 1,
                    "score": 0.8,
                    "score_breakdown": {
                        "bm25": 0.7,
                        "intent": 0.9,
                        "popularity": 0.2,
                        "personal": 0.5,
                    },
                    "categories": ["파스타"],
                    "menus": ["알리오올리오"],
                }
            ],
        },
        {
            "event_type": "feedback",
            "session_id": "session-a",
            "shop_id": "shop-1",
            "action": "like",
            "profile": {"regions": ["강남"]},
            "shop": {"shop_id": "shop-1"},
        },
    ]
    input_path.write_text(
        "\n".join(json.dumps(event, ensure_ascii=False) for event in events),
        encoding="utf-8",
    )

    summary = export_training_dataset(input_path, output_path)
    samples = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    ]

    assert summary == {"events": 2, "samples": 1, "positive": 1, "negative": 0}
    assert samples[0]["query"] == "강남 파스타 추천해줘"
    assert samples[0]["label"] == 1.0
    assert samples[0]["features"]["bm25"] == 0.7
    assert samples[0]["shop"]["categories"] == ["파스타"]


def test_tune_chatbot_rank_weights_returns_best_report(tmp_path):
    input_path = tmp_path / "training.jsonl"
    output_path = tmp_path / "rank_weight_report.json"
    samples = [
        {
            "query": "강남 파스타",
            "shop_id": "positive-a",
            "label": 1.0,
            "features": {"bm25": 0.9, "intent": 0.1, "popularity": 0.1, "personal": 0.1},
        },
        {
            "query": "강남 파스타",
            "shop_id": "negative-a",
            "label": 0.0,
            "features": {"bm25": 0.1, "intent": 0.9, "popularity": 0.9, "personal": 0.1},
        },
        {
            "query": "성수 카페",
            "shop_id": "positive-b",
            "label": 1.0,
            "features": {"bm25": 0.8, "intent": 0.2, "popularity": 0.1, "personal": 0.2},
        },
        {
            "query": "성수 카페",
            "shop_id": "negative-b",
            "label": 0.0,
            "features": {"bm25": 0.2, "intent": 0.8, "popularity": 0.8, "personal": 0.1},
        },
    ]
    input_path.write_text(
        "\n".join(json.dumps(sample, ensure_ascii=False) for sample in samples),
        encoding="utf-8",
    )

    report = tune_rank_weights(
        input_path,
        output_path=output_path,
        top_k=1,
        step=0.5,
        min_groups=1,
    )

    assert report["status"] == "ok"
    assert report["eligible_groups"] == 2
    assert report["best_metrics"]["ndcg@1"] == 1.0
    assert output_path.exists()


def test_tune_chatbot_rank_weights_handles_insufficient_data(tmp_path):
    input_path = tmp_path / "training.jsonl"
    input_path.write_text(
        json.dumps(
            {
                "query": "강남 파스타",
                "shop_id": "only-one",
                "label": 1.0,
                "features": {"bm25": 0.8},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = tune_rank_weights(input_path, top_k=5, step=0.5, min_groups=1)

    assert report["status"] == "insufficient_data"
    assert report["eligible_groups"] == 0


def test_recommendation_evaluation_metrics_are_stable():
    assert _percentile([4, 1, 3, 2], 50) == 2
    assert _percentile([4, 1, 3, 2], 95) == 4
    assert _ndcg(["shop-a", "shop-b"], {"shop-a": 1.0}, 2) == 1.0
    assert _mrr(["shop-b", "shop-a"], {"shop-a"}, 2) == 0.5
