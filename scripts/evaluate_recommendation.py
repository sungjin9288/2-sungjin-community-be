"""
scripts/evaluate_recommendation.py

추천 모델의 랭킹 품질과 추론 속도를 측정한다.

기본 사용법:
    python scripts/evaluate_recommendation.py

전체 로그 기반 평가:
    python scripts/evaluate_recommendation.py --max-rows 0 --max-queries 200
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


def _read_logs(path: Path, max_rows: int) -> pd.DataFrame:
    nrows = None if max_rows <= 0 else max_rows
    return pd.read_csv(path, encoding="utf-8-sig", nrows=nrows)


def main() -> None:
    parser = argparse.ArgumentParser(description="추천 모델 NDCG/MRR/latency 평가")
    parser.add_argument("--logs", default="data/logs.csv", help="logs.csv 경로")
    parser.add_argument("--shops", default="data/shops.csv", help="shops.csv 경로")
    parser.add_argument("--cache", default="data/log_cache.pkl", help="log_cache.pkl 경로")
    parser.add_argument("--top-k", type=int, default=5, help="평가 cutoff")
    parser.add_argument("--max-rows", type=int, default=500_000, help="평가용 로그 행 수. 0이면 전체")
    parser.add_argument("--max-queries", type=int, default=100, help="평가 query 수")
    args = parser.parse_args()

    logs_path = Path(args.logs)
    if not logs_path.exists():
        raise SystemExit(f"logs.csv 없음: {logs_path}")

    os.environ["SHOPS_CSV_PATH"] = args.shops
    os.environ["LOG_CACHE_PATH"] = args.cache
    recommendation_engine.load(shops_path=args.shops, logs_path=args.logs)

    logs_df = _read_logs(logs_path, args.max_rows)
    events = _propagate_queries_and_aggregate(logs_df)
    if events.empty:
        raise SystemExit("평가 가능한 이벤트가 없습니다.")

    events["query_key"] = events["search_query"].map(_normalize_query)
    events = events[events["query_key"] != ""]
    grouped = events.groupby(["query_key", "shop_id"], as_index=False)["weight"].sum()
    totals = grouped.groupby("query_key")["weight"].sum().sort_values(ascending=False)
    query_keys = totals.head(args.max_queries).index.tolist()

    ndcgs: list[float] = []
    mrrs: list[float] = []
    latencies_ms: list[float] = []

    for query_key in query_keys:
        rel_rows = grouped[grouped["query_key"] == query_key]
        relevance_map = dict(zip(rel_rows["shop_id"], rel_rows["weight"], strict=False))
        max_rel = max(relevance_map.values()) or 1.0
        relevance_map = {shop_id: rel / max_rel for shop_id, rel in relevance_map.items()}
        relevant_ids = set(relevance_map)

        t0 = time.perf_counter()
        recommended = recommendation_engine.recommend(query_key, top_k=args.top_k)
        latencies_ms.append((time.perf_counter() - t0) * 1000)

        recommended_ids = [str(item.get("shop_id", "")) for item in recommended]
        ndcgs.append(_ndcg(recommended_ids, relevance_map, args.top_k))
        mrrs.append(_mrr(recommended_ids, relevant_ids, args.top_k))

    result = {
        "queries": len(query_keys),
        "top_k": args.top_k,
        "max_rows": "all" if args.max_rows <= 0 else args.max_rows,
        f"ndcg@{args.top_k}": round(sum(ndcgs) / len(ndcgs), 4),
        f"mrr@{args.top_k}": round(sum(mrrs) / len(mrrs), 4),
        "avg_latency_ms": round(sum(latencies_ms) / len(latencies_ms), 3),
        "p95_latency_ms": round(sorted(latencies_ms)[int(len(latencies_ms) * 0.95) - 1], 3),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
