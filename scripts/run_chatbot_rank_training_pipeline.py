"""
scripts/run_chatbot_rank_training_pipeline.py

추천 랭킹 학습 파이프라인을 한 번에 실행한다.

순서:
  1. 기존 행동 로그로 weak-label 학습셋 생성
  2. 학습셋으로 rank weight 후보 튜닝
  3. 기준 성능을 통과한 후보만 서버 적용 artifact로 승격

사용법:
    python scripts/run_chatbot_rank_training_pipeline.py \
      --max-rows 500000 \
      --max-queries 200 \
      --candidate-k 50
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build_recommendation_training_dataset import (
    build_recommendation_training_dataset,
)
from scripts.promote_chatbot_rank_weights import promote_rank_weight_report
from scripts.tune_chatbot_rank_weights import tune_rank_weights


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_rank_training_pipeline(
    *,
    logs_path: Path,
    shops_path: str,
    cache_path: str,
    training_output_path: Path,
    candidate_output_path: Path,
    artifact_output_path: Path,
    decision_output_path: Path,
    summary_output_path: Path | None = None,
    max_rows: int = 500_000,
    max_queries: int = 200,
    candidate_k: int = 50,
    min_positive_per_query: int = 1,
    top_k: int = 5,
    step: float = 0.1,
    tune_min_groups: int = 3,
    promote_metric: str = "ndcg",
    promote_min_samples: int = 100,
    promote_min_groups: int = 3,
    promote_min_improvement: float = 0.0001,
) -> dict[str, Any]:
    dataset_summary = build_recommendation_training_dataset(
        logs_path=logs_path,
        shops_path=shops_path,
        cache_path=cache_path,
        output_path=training_output_path,
        max_rows=max_rows,
        max_queries=max_queries,
        candidate_k=candidate_k,
        min_positive_per_query=min_positive_per_query,
    )
    tune_report = tune_rank_weights(
        training_output_path,
        output_path=candidate_output_path,
        top_k=top_k,
        step=step,
        min_groups=tune_min_groups,
    )
    promotion_decision = promote_rank_weight_report(
        candidate_output_path,
        artifact_output_path,
        metric=promote_metric,
        min_samples=promote_min_samples,
        min_groups=promote_min_groups,
        min_improvement=promote_min_improvement,
        decision_output_path=decision_output_path,
    )

    summary = {
        "status": promotion_decision.get("status", "unknown"),
        "dataset": dataset_summary,
        "tuning": {
            "status": tune_report.get("status"),
            "active_features": tune_report.get("active_features") or [],
            "baseline_metrics": tune_report.get("baseline_metrics") or {},
            "best_metrics": tune_report.get("best_metrics") or {},
            "best_weights": tune_report.get("best_weights"),
        },
        "promotion": promotion_decision,
        "outputs": {
            "training_samples": str(training_output_path),
            "candidate_report": str(candidate_output_path),
            "artifact": str(artifact_output_path),
            "decision": str(decision_output_path),
            "summary": str(summary_output_path) if summary_output_path else None,
        },
    }
    if summary_output_path:
        _write_json(summary_output_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="챗봇 추천 랭킹 학습 파이프라인 실행")
    parser.add_argument("--logs", default="data/logs.csv", help="logs.csv 경로")
    parser.add_argument("--shops", default="data/shops.csv", help="shops.csv 경로")
    parser.add_argument("--cache", default="data/log_cache.pkl", help="log_cache.pkl 경로")
    parser.add_argument("--training-output", default="data/recommendation_training_samples.jsonl", help="학습 샘플 JSONL")
    parser.add_argument("--candidate-output", default="data/chatbot_rank_weight_candidate.json", help="튜닝 후보 JSON")
    parser.add_argument("--artifact-output", default="data/chatbot_rank_weight_report.json", help="서버 적용 artifact JSON")
    parser.add_argument("--decision-output", default="data/chatbot_rank_weight_decision.json", help="승격 판단 JSON")
    parser.add_argument("--summary-output", default="data/chatbot_rank_weight_pipeline_report.json", help="파이프라인 요약 JSON")
    parser.add_argument("--max-rows", type=int, default=500_000, help="사용할 로그 행 수. 0이면 전체")
    parser.add_argument("--max-queries", type=int, default=200, help="상위 query 수. 0이면 전체")
    parser.add_argument("--candidate-k", type=int, default=50, help="query별 추천 후보 수")
    parser.add_argument("--min-positive-per-query", type=int, default=1, help="query별 최소 positive 후보 수")
    parser.add_argument("--top-k", type=int, default=5, help="튜닝 평가 cutoff")
    parser.add_argument("--step", type=float, default=0.1, help="가중치 grid search step")
    parser.add_argument("--tune-min-groups", type=int, default=3, help="튜닝 최소 query 그룹 수")
    parser.add_argument("--promote-metric", default="ndcg", choices=["ndcg", "mrr", "hit_rate"], help="승격 기준 metric")
    parser.add_argument("--promote-min-samples", type=int, default=100, help="승격 최소 샘플 수")
    parser.add_argument("--promote-min-groups", type=int, default=3, help="승격 최소 query 그룹 수")
    parser.add_argument("--promote-min-improvement", type=float, default=0.0001, help="승격 최소 개선폭")
    args = parser.parse_args()

    try:
        summary = run_rank_training_pipeline(
            logs_path=Path(args.logs),
            shops_path=args.shops,
            cache_path=args.cache,
            training_output_path=Path(args.training_output),
            candidate_output_path=Path(args.candidate_output),
            artifact_output_path=Path(args.artifact_output),
            decision_output_path=Path(args.decision_output),
            summary_output_path=Path(args.summary_output) if args.summary_output else None,
            max_rows=args.max_rows,
            max_queries=args.max_queries,
            candidate_k=args.candidate_k,
            min_positive_per_query=args.min_positive_per_query,
            top_k=args.top_k,
            step=args.step,
            tune_min_groups=args.tune_min_groups,
            promote_metric=args.promote_metric,
            promote_min_samples=args.promote_min_samples,
            promote_min_groups=args.promote_min_groups,
            promote_min_improvement=args.promote_min_improvement,
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
