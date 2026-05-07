"""
scripts/evaluate_recommendation.py

추천 모델의 랭킹 품질과 추론 속도를 측정한다.

기본 사용법:
    python scripts/evaluate_recommendation.py

전체 로그 기반 평가:
    python scripts/evaluate_recommendation.py --max-rows 0 --max-queries 200

JSON 리포트 저장:
    python scripts/evaluate_recommendation.py --output data/recommendation_eval_report.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.chatbot.recommendation_engine import (  # noqa: E402
    _normalize_query,
    _propagate_queries_and_aggregate,
    recommendation_engine,
)


def _dcg(relevances: list[float]) -> float:
    return sum(rel / math.log2(rank + 2) for rank, rel in enumerate(relevances))


def _ndcg(recommended_ids: list[str], relevance_map: dict[str, float], top_k: int) -> float:
    gains = [relevance_map.get(shop_id, 0.0) for shop_id in recommended_ids[:top_k]]
    ideal = sorted(relevance_map.values(), reverse=True)[:top_k]
    ideal_dcg = _dcg(ideal)
    if ideal_dcg <= 0:
        return 0.0
    return _dcg(gains) / ideal_dcg


def _mrr(recommended_ids: list[str], relevant_ids: set[str], top_k: int) -> float:
    for rank, shop_id in enumerate(recommended_ids[:top_k], start=1):
        if shop_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = math.ceil((percentile / 100) * len(ordered)) - 1
    index = max(0, min(index, len(ordered) - 1))
    return ordered[index]


def _read_logs(path: Path, max_rows: int) -> pd.DataFrame:
    nrows = None if max_rows <= 0 else max_rows
    return pd.read_csv(path, encoding="utf-8-sig", nrows=nrows)


def evaluate_recommendation(
    *,
    logs_path: Path,
    shops_path: str,
    cache_path: str,
    top_k: int,
    max_rows: int,
    max_queries: int,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    if not logs_path.exists():
        raise FileNotFoundError(f"logs.csv 없음: {logs_path}")

    os.environ["SHOPS_CSV_PATH"] = shops_path
    os.environ["LOG_CACHE_PATH"] = cache_path
    recommendation_engine.load(shops_path=shops_path, logs_path=str(logs_path))

    logs_df = _read_logs(logs_path, max_rows)
    events = _propagate_queries_and_aggregate(logs_df)
    if events.empty:
        raise ValueError("평가 가능한 이벤트가 없습니다.")

    events["query_key"] = events["search_query"].map(_normalize_query)
    events = events[events["query_key"] != ""]
    grouped = events.groupby(["query_key", "shop_id"], as_index=False)["weight"].sum()
    totals = grouped.groupby("query_key")["weight"].sum().sort_values(ascending=False)
    query_keys = totals.head(max_queries).index.tolist()

    ndcgs: list[float] = []
    mrrs: list[float] = []
    hit_rates: list[float] = []
    latencies_ms: list[float] = []
    zero_results = 0
    recommended_shop_ids: set[str] = set()
    details: list[dict[str, object]] = []

    for query_key in query_keys:
        rel_rows = grouped[grouped["query_key"] == query_key]
        relevance_map = dict(zip(rel_rows["shop_id"], rel_rows["weight"], strict=False))
        max_rel = max(relevance_map.values()) or 1.0
        relevance_map = {shop_id: rel / max_rel for shop_id, rel in relevance_map.items()}
        relevant_ids = set(relevance_map)

        t0 = time.perf_counter()
        recommended = recommendation_engine.recommend(query_key, top_k=top_k)
        latency_ms = (time.perf_counter() - t0) * 1000
        latencies_ms.append(latency_ms)

        recommended_ids = [str(item.get("shop_id", "")) for item in recommended]
        recommended_shop_ids.update(shop_id for shop_id in recommended_ids if shop_id)
        if not recommended_ids:
            zero_results += 1

        ndcg_value = _ndcg(recommended_ids, relevance_map, top_k)
        mrr_value = _mrr(recommended_ids, relevant_ids, top_k)
        hit_value = 1.0 if relevant_ids.intersection(recommended_ids[:top_k]) else 0.0
        ndcgs.append(ndcg_value)
        mrrs.append(mrr_value)
        hit_rates.append(hit_value)
        details.append(
            {
                "query": query_key,
                f"ndcg@{top_k}": round(ndcg_value, 4),
                f"mrr@{top_k}": round(mrr_value, 4),
                f"hit_rate@{top_k}": round(hit_value, 4),
                "latency_ms": round(latency_ms, 3),
                "recommended_count": len(recommended_ids),
                "relevant_count": len(relevant_ids),
                "recommended_ids": recommended_ids[:top_k],
            }
        )

    query_count = len(query_keys)
    shop_count = recommendation_engine.shop_count
    report = {
        "queries": query_count,
        "top_k": top_k,
        "max_rows": "all" if max_rows <= 0 else max_rows,
        "candidate_events": int(len(events)),
        "unique_relevant_shops": int(grouped["shop_id"].nunique()),
        "shop_count": int(shop_count),
        f"ndcg@{top_k}": round(_mean(ndcgs), 4),
        f"mrr@{top_k}": round(_mean(mrrs), 4),
        f"hit_rate@{top_k}": round(_mean(hit_rates), 4),
        f"coverage@{top_k}": round(len(recommended_shop_ids) / shop_count, 4) if shop_count else 0.0,
        "zero_result_rate": round(zero_results / query_count, 4) if query_count else 0.0,
        "avg_latency_ms": round(_mean(latencies_ms), 3),
        "p50_latency_ms": round(_percentile(latencies_ms, 50), 3),
        "p95_latency_ms": round(_percentile(latencies_ms, 95), 3),
        "max_latency_ms": round(max(latencies_ms), 3) if latencies_ms else 0.0,
    }
    return report, details


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="추천 모델 NDCG/MRR/latency 평가")
    parser.add_argument("--logs", default="data/logs.csv", help="logs.csv 경로")
    parser.add_argument("--shops", default="data/shops.csv", help="shops.csv 경로")
    parser.add_argument("--cache", default="data/log_cache.pkl", help="log_cache.pkl 경로")
    parser.add_argument("--top-k", type=int, default=5, help="평가 cutoff")
    parser.add_argument("--max-rows", type=int, default=500_000, help="평가용 로그 행 수. 0이면 전체")
    parser.add_argument("--max-queries", type=int, default=100, help="평가 query 수")
    parser.add_argument("--output", default="", help="요약 JSON 리포트 저장 경로")
    parser.add_argument("--details-output", default="", help="query별 JSONL 리포트 저장 경로")
    args = parser.parse_args()

    logs_path = Path(args.logs)
    try:
        report, details = evaluate_recommendation(
            logs_path=logs_path,
            shops_path=args.shops,
            cache_path=args.cache,
            top_k=args.top_k,
            max_rows=args.max_rows,
            max_queries=args.max_queries,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    if args.output:
        _write_json(Path(args.output), report)
    if args.details_output:
        _write_jsonl(Path(args.details_output), details)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
