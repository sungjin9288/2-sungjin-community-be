import json

from scripts.export_chatbot_learning_dataset import export_training_dataset


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
