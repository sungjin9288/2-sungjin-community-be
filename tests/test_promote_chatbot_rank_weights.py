import json

from scripts.promote_chatbot_rank_weights import promote_rank_weight_report


def _report(*, best_ndcg=0.7, baseline_ndcg=0.6, status="ok"):
    return {
        "status": status,
        "samples": 120,
        "eligible_groups": 4,
        "top_k": 5,
        "active_features": ["bm25", "intent"],
        "best_weights": {"bm25": 0.6, "intent": 0.4, "popularity": 0.0, "personal": 0.0},
        "baseline_metrics": {"ndcg@5": baseline_ndcg, "mrr@5": 0.5},
        "best_metrics": {"ndcg@5": best_ndcg, "mrr@5": 0.55},
    }


def test_promote_rank_weight_report_writes_output_when_improved(tmp_path):
    input_path = tmp_path / "candidate.json"
    output_path = tmp_path / "artifact.json"
    decision_path = tmp_path / "decision.json"
    input_path.write_text(json.dumps(_report()), encoding="utf-8")

    decision = promote_rank_weight_report(
        input_path,
        output_path,
        min_samples=100,
        min_groups=3,
        min_improvement=0.01,
        decision_output_path=decision_path,
    )
    promoted = json.loads(output_path.read_text(encoding="utf-8"))
    saved_decision = json.loads(decision_path.read_text(encoding="utf-8"))

    assert decision["status"] == "promoted"
    assert decision["improvement"] == 0.1
    assert promoted["status"] == "ok"
    assert promoted["promotion"]["status"] == "promoted"
    assert promoted["promotion"]["metric"] == "ndcg@5"
    assert saved_decision["status"] == "promoted"


def test_promote_rank_weight_report_rejects_when_not_improved(tmp_path):
    input_path = tmp_path / "candidate.json"
    output_path = tmp_path / "artifact.json"
    input_path.write_text(
        json.dumps(_report(best_ndcg=0.6001, baseline_ndcg=0.6)),
        encoding="utf-8",
    )

    decision = promote_rank_weight_report(
        input_path,
        output_path,
        min_samples=100,
        min_groups=3,
        min_improvement=0.01,
    )

    assert decision["status"] == "rejected"
    assert decision["reason"] == "improvement<0.01"
    assert output_path.exists() is False


def test_promote_rank_weight_report_rejects_insufficient_data(tmp_path):
    input_path = tmp_path / "candidate.json"
    output_path = tmp_path / "artifact.json"
    report = _report()
    report["samples"] = 20
    input_path.write_text(json.dumps(report), encoding="utf-8")

    decision = promote_rank_weight_report(
        input_path,
        output_path,
        min_samples=100,
        min_groups=3,
    )

    assert decision["status"] == "rejected"
    assert decision["reason"] == "samples<100"
    assert output_path.exists() is False


def test_promote_rank_weight_report_rejects_inactive_tune_report(tmp_path):
    input_path = tmp_path / "candidate.json"
    output_path = tmp_path / "artifact.json"
    input_path.write_text(
        json.dumps(_report(status="insufficient_data")),
        encoding="utf-8",
    )

    decision = promote_rank_weight_report(input_path, output_path, min_samples=1)

    assert decision["status"] == "rejected"
    assert decision["reason"] == "report_status=insufficient_data"
    assert output_path.exists() is False
