import json

from scripts import run_chatbot_rank_training_pipeline as pipeline


def test_run_rank_training_pipeline_promotes_candidate(tmp_path, monkeypatch):
    calls = []

    def fake_build(**kwargs):
        calls.append(("build", kwargs))
        return {"samples": 120, "queries_included": 4}

    def fake_tune(input_path, *, output_path, top_k, step, min_groups):
        calls.append(("tune", input_path, output_path, top_k, step, min_groups))
        report = {
            "status": "ok",
            "active_features": ["bm25", "intent"],
            "baseline_metrics": {"ndcg@5": 0.5},
            "best_metrics": {"ndcg@5": 0.55},
            "best_weights": {"bm25": 0.6, "intent": 0.4, "popularity": 0.0, "personal": 0.0},
        }
        output_path.write_text(json.dumps(report), encoding="utf-8")
        return report

    def fake_promote(input_path, output_path, **kwargs):
        calls.append(("promote", input_path, output_path, kwargs))
        output_path.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
        return {
            "status": "promoted",
            "metric": "ndcg@5",
            "baseline": 0.5,
            "best": 0.55,
            "improvement": 0.05,
        }

    monkeypatch.setattr(pipeline, "build_recommendation_training_dataset", fake_build)
    monkeypatch.setattr(pipeline, "tune_rank_weights", fake_tune)
    monkeypatch.setattr(pipeline, "promote_rank_weight_report", fake_promote)

    summary = pipeline.run_rank_training_pipeline(
        logs_path=tmp_path / "logs.csv",
        shops_path="shops.csv",
        cache_path="cache.pkl",
        training_output_path=tmp_path / "training.jsonl",
        candidate_output_path=tmp_path / "candidate.json",
        artifact_output_path=tmp_path / "artifact.json",
        decision_output_path=tmp_path / "decision.json",
        summary_output_path=tmp_path / "summary.json",
        max_rows=100,
        max_queries=10,
        candidate_k=20,
        min_positive_per_query=1,
        top_k=5,
        step=0.1,
        tune_min_groups=3,
        promote_metric="ndcg",
        promote_min_samples=100,
        promote_min_groups=3,
        promote_min_improvement=0.001,
    )
    saved_summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))

    assert summary["status"] == "promoted"
    assert summary["dataset"]["samples"] == 120
    assert summary["tuning"]["best_metrics"]["ndcg@5"] == 0.55
    assert summary["promotion"]["status"] == "promoted"
    assert saved_summary["status"] == "promoted"
    assert calls[0][0] == "build"
    assert calls[1][0] == "tune"
    assert calls[2][0] == "promote"


def test_run_rank_training_pipeline_keeps_rejection_status(tmp_path, monkeypatch):
    def fake_build(**kwargs):
        return {"samples": 20, "queries_included": 1}

    def fake_tune(input_path, *, output_path, top_k, step, min_groups):
        return {
            "status": "insufficient_data",
            "active_features": [],
            "baseline_metrics": {},
            "best_metrics": {},
            "best_weights": None,
        }

    def fake_promote(input_path, output_path, **kwargs):
        return {
            "status": "rejected",
            "reason": "report_status=insufficient_data",
        }

    monkeypatch.setattr(pipeline, "build_recommendation_training_dataset", fake_build)
    monkeypatch.setattr(pipeline, "tune_rank_weights", fake_tune)
    monkeypatch.setattr(pipeline, "promote_rank_weight_report", fake_promote)

    summary = pipeline.run_rank_training_pipeline(
        logs_path=tmp_path / "logs.csv",
        shops_path="shops.csv",
        cache_path="cache.pkl",
        training_output_path=tmp_path / "training.jsonl",
        candidate_output_path=tmp_path / "candidate.json",
        artifact_output_path=tmp_path / "artifact.json",
        decision_output_path=tmp_path / "decision.json",
    )

    assert summary["status"] == "rejected"
    assert summary["promotion"]["reason"] == "report_status=insufficient_data"
    assert summary["tuning"]["status"] == "insufficient_data"
