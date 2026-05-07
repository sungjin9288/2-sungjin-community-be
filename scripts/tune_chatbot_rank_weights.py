"""
scripts/tune_chatbot_rank_weights.py

챗봇 피드백 학습 샘플(JSONL)을 사용해 추천 점수 가중치를 grid search로 실험한다.
모델 artifact를 만들기 전 단계의 가벼운 baseline 실험용이며, 데이터가 부족하면
insufficient_data 상태를 반환한다.

사용법:
    python scripts/tune_chatbot_rank_weights.py \
      --input data/chatbot_training_samples.jsonl \
      --output data/chatbot_rank_weight_report.json
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

FEATURES = ("bm25", "intent", "popularity", "personal")
BASELINE_WEIGHTS = {
    "bm25": 0.35,
    "intent": 0.30,
    "popularity": 0.15,
    "personal": 0.20,
}


def _read_samples(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    samples: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                sample = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(sample, dict):
                samples.append(sample)
    return samples


def _numeric(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(number) or math.isinf(number):
        return 0.0
    return number


def _valid_sample(sample: dict[str, Any]) -> bool:
    query = str(sample.get("query") or "").strip()
    shop_id = str(sample.get("shop_id") or "").strip()
    label = sample.get("label")
    return bool(query and shop_id and label is not None)


def _group_samples(samples: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        if _valid_sample(sample):
            groups[str(sample.get("query")).strip()].append(sample)
    return dict(groups)


def _eligible_groups(groups: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    eligible = {}
    for query, rows in groups.items():
        if len(rows) < 2:
            continue
        labels = [_numeric(row.get("label")) for row in rows]
        if max(labels) <= 0:
            continue
        eligible[query] = rows
    return eligible


def _score_sample(sample: dict[str, Any], weights: dict[str, float]) -> float:
    features = sample.get("features") if isinstance(sample.get("features"), dict) else {}
    return sum(weights[feature] * _numeric(features.get(feature)) for feature in FEATURES)


def _dcg(labels: list[float]) -> float:
    return sum(label / math.log2(rank + 2) for rank, label in enumerate(labels))


def _ndcg(sorted_labels: list[float], top_k: int) -> float:
    gains = sorted_labels[:top_k]
    ideal = sorted(sorted_labels, reverse=True)[:top_k]
    ideal_dcg = _dcg(ideal)
    return _dcg(gains) / ideal_dcg if ideal_dcg > 0 else 0.0


def _mrr(sorted_labels: list[float], top_k: int) -> float:
    for rank, label in enumerate(sorted_labels[:top_k], start=1):
        if label > 0:
            return 1.0 / rank
    return 0.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _evaluate_weights(
    groups: dict[str, list[dict[str, Any]]],
    weights: dict[str, float],
    top_k: int,
) -> dict[str, float]:
    ndcgs: list[float] = []
    mrrs: list[float] = []
    hit_rates: list[float] = []

    for rows in groups.values():
        ranked = sorted(rows, key=lambda row: _score_sample(row, weights), reverse=True)
        labels = [_numeric(row.get("label")) for row in ranked]
        ndcgs.append(_ndcg(labels, top_k))
        mrrs.append(_mrr(labels, top_k))
        hit_rates.append(1.0 if any(label > 0 for label in labels[:top_k]) else 0.0)

    return {
        f"ndcg@{top_k}": round(_mean(ndcgs), 4),
        f"mrr@{top_k}": round(_mean(mrrs), 4),
        f"hit_rate@{top_k}": round(_mean(hit_rates), 4),
    }


def _active_features(groups: dict[str, list[dict[str, Any]]]) -> tuple[str, ...]:
    active: list[str] = []
    for feature in FEATURES:
        values: list[float] = []
        for rows in groups.values():
            for row in rows:
                features = row.get("features") if isinstance(row.get("features"), dict) else {}
                values.append(_numeric(features.get(feature)))
        if values and max(values) > min(values):
            active.append(feature)
    return tuple(active)


def _normalise_weights_for_features(
    weights: dict[str, float],
    active_features: tuple[str, ...],
) -> dict[str, float]:
    if not active_features:
        return {feature: 0.0 for feature in FEATURES}
    total = sum(weights.get(feature, 0.0) for feature in active_features)
    if total <= 0:
        return {
            feature: round(1.0 / len(active_features), 6) if feature in active_features else 0.0
            for feature in FEATURES
        }
    return {
        feature: round(weights.get(feature, 0.0) / total, 6) if feature in active_features else 0.0
        for feature in FEATURES
    }


def _weight_grid(step: float, active_features: tuple[str, ...] = FEATURES) -> list[dict[str, float]]:
    if step <= 0 or step > 1:
        raise ValueError("--step must be in (0, 1]")
    units = round(1.0 / step)
    if not math.isclose(units * step, 1.0, abs_tol=1e-9):
        raise ValueError("--step must divide 1.0 exactly, e.g. 0.5, 0.25, 0.2, 0.1")
    if not active_features:
        return []

    grid: list[dict[str, float]] = []

    def walk(remaining_units: int, depth: int, values: list[int]) -> None:
        if depth == len(active_features) - 1:
            active_weights = {
                feature: round(value * step, 6)
                for feature, value in zip(active_features, [*values, remaining_units], strict=True)
            }
            grid.append({feature: active_weights.get(feature, 0.0) for feature in FEATURES})
            return
        for value in range(remaining_units + 1):
            walk(remaining_units - value, depth + 1, [*values, value])

    walk(units, 0, [])
    return grid


def tune_rank_weights(
    input_path: Path,
    *,
    output_path: Path | None = None,
    top_k: int = 5,
    step: float = 0.1,
    min_groups: int = 1,
) -> dict[str, Any]:
    samples = _read_samples(input_path)
    groups = _eligible_groups(_group_samples(samples))
    active_features = _active_features(groups)
    report: dict[str, Any] = {
        "input": str(input_path),
        "samples": len(samples),
        "eligible_groups": len(groups),
        "top_k": top_k,
        "step": step,
        "active_features": list(active_features),
        "baseline_weights": BASELINE_WEIGHTS,
    }

    if len(groups) < min_groups:
        report.update(
            {
                "status": "insufficient_data",
                "reason": f"eligible_groups<{min_groups}",
                "baseline_metrics": {},
                "best_weights": None,
                "best_metrics": {},
            }
        )
    elif not active_features:
        report.update(
            {
                "status": "insufficient_data",
                "reason": "no_active_feature_variance",
                "baseline_metrics": {},
                "best_weights": None,
                "best_metrics": {},
            }
        )
    else:
        comparable_baseline = _normalise_weights_for_features(BASELINE_WEIGHTS, active_features)
        baseline_metrics = _evaluate_weights(groups, comparable_baseline, top_k)
        best_weights = comparable_baseline
        best_metrics = baseline_metrics
        best_key = (
            best_metrics[f"ndcg@{top_k}"],
            best_metrics[f"mrr@{top_k}"],
            best_metrics[f"hit_rate@{top_k}"],
        )

        for weights in _weight_grid(step, active_features):
            metrics = _evaluate_weights(groups, weights, top_k)
            key = (
                metrics[f"ndcg@{top_k}"],
                metrics[f"mrr@{top_k}"],
                metrics[f"hit_rate@{top_k}"],
            )
            if key > best_key:
                best_key = key
                best_weights = weights
                best_metrics = metrics

        report.update(
            {
                "status": "ok",
                "comparable_baseline_weights": comparable_baseline,
                "baseline_metrics": baseline_metrics,
                "best_weights": best_weights,
                "best_metrics": best_metrics,
            }
        )

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="챗봇 피드백 기반 추천 가중치 튜닝")
    parser.add_argument("--input", default="data/chatbot_training_samples.jsonl", help="학습 샘플 JSONL")
    parser.add_argument("--output", default="", help="튜닝 리포트 JSON 저장 경로")
    parser.add_argument("--top-k", type=int, default=5, help="평가 cutoff")
    parser.add_argument("--step", type=float, default=0.1, help="grid search step")
    parser.add_argument("--min-groups", type=int, default=3, help="실험에 필요한 최소 query 그룹 수")
    args = parser.parse_args()

    try:
        report = tune_rank_weights(
            Path(args.input),
            output_path=Path(args.output) if args.output else None,
            top_k=args.top_k,
            step=args.step,
            min_groups=args.min_groups,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
