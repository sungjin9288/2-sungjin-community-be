"""
scripts/promote_chatbot_rank_weights.py

튜닝 리포트를 검증한 뒤 서버가 읽는 추천 랭킹 가중치 artifact로 승격한다.
데이터가 부족하거나 baseline 대비 개선이 없으면 출력 artifact를 덮어쓰지 않는다.

사용법:
    python scripts/promote_chatbot_rank_weights.py \
      --input data/chatbot_rank_weight_candidate.json \
      --output data/chatbot_rank_weight_report.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"튜닝 리포트 없음: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"튜닝 리포트 형식 오류: {path}")
    return payload


def _numeric(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _metric_key(report: dict[str, Any], metric: str) -> str:
    top_k = int(report.get("top_k") or 5)
    return f"{metric}@{top_k}"


def _decision(
    report: dict[str, Any],
    *,
    metric: str,
    min_samples: int,
    min_groups: int,
    min_improvement: float,
) -> dict[str, Any]:
    key = _metric_key(report, metric)
    baseline_metrics = report.get("baseline_metrics") if isinstance(report.get("baseline_metrics"), dict) else {}
    best_metrics = report.get("best_metrics") if isinstance(report.get("best_metrics"), dict) else {}
    baseline = _numeric(baseline_metrics.get(key))
    best = _numeric(best_metrics.get(key))
    improvement = round(best - baseline, 6)
    samples = int(report.get("samples") or 0)
    eligible_groups = int(report.get("eligible_groups") or 0)

    decision = {
        "status": "rejected",
        "metric": key,
        "baseline": baseline,
        "best": best,
        "improvement": improvement,
        "min_improvement": min_improvement,
        "samples": samples,
        "min_samples": min_samples,
        "eligible_groups": eligible_groups,
        "min_groups": min_groups,
        "reason": "",
    }

    if report.get("status") != "ok":
        decision["reason"] = f"report_status={report.get('status')}"
    elif samples < min_samples:
        decision["reason"] = f"samples<{min_samples}"
    elif eligible_groups < min_groups:
        decision["reason"] = f"eligible_groups<{min_groups}"
    elif key not in baseline_metrics or key not in best_metrics:
        decision["reason"] = f"missing_metric={key}"
    elif improvement < min_improvement:
        decision["reason"] = f"improvement<{min_improvement}"
    elif not isinstance(report.get("best_weights"), dict):
        decision["reason"] = "missing_best_weights"
    else:
        decision["status"] = "promoted"
        decision["reason"] = "passed"

    return decision


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def promote_rank_weight_report(
    input_path: Path,
    output_path: Path,
    *,
    metric: str = "ndcg",
    min_samples: int = 100,
    min_groups: int = 3,
    min_improvement: float = 0.0001,
    decision_output_path: Path | None = None,
) -> dict[str, Any]:
    report = _read_json(input_path)
    decision = _decision(
        report,
        metric=metric,
        min_samples=min_samples,
        min_groups=min_groups,
        min_improvement=min_improvement,
    )
    decision["input"] = str(input_path)
    decision["output"] = str(output_path)

    if decision["status"] == "promoted":
        promoted = dict(report)
        promoted["promotion"] = {
            "status": "promoted",
            "metric": decision["metric"],
            "baseline": decision["baseline"],
            "best": decision["best"],
            "improvement": decision["improvement"],
            "min_improvement": decision["min_improvement"],
            "source_report": str(input_path),
        }
        _write_json(output_path, promoted)
    if decision_output_path:
        _write_json(decision_output_path, decision)
    return decision


def main() -> None:
    parser = argparse.ArgumentParser(description="튜닝 리포트를 추천 랭킹 가중치 artifact로 승격")
    parser.add_argument("--input", default="data/chatbot_rank_weight_candidate.json", help="튜닝 후보 리포트 JSON")
    parser.add_argument("--output", default="data/chatbot_rank_weight_report.json", help="서버가 읽을 artifact JSON")
    parser.add_argument("--decision-output", default="", help="승격/거절 판단 결과 JSON 저장 경로")
    parser.add_argument("--metric", default="ndcg", choices=["ndcg", "mrr", "hit_rate"], help="승격 기준 metric")
    parser.add_argument("--min-samples", type=int, default=100, help="승격에 필요한 최소 샘플 수")
    parser.add_argument("--min-groups", type=int, default=3, help="승격에 필요한 최소 query 그룹 수")
    parser.add_argument("--min-improvement", type=float, default=0.0001, help="baseline 대비 최소 개선폭")
    args = parser.parse_args()

    try:
        decision = promote_rank_weight_report(
            Path(args.input),
            Path(args.output),
            metric=args.metric,
            min_samples=args.min_samples,
            min_groups=args.min_groups,
            min_improvement=args.min_improvement,
            decision_output_path=Path(args.decision_output) if args.decision_output else None,
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc

    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
