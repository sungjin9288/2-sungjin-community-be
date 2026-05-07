"""
scripts/build_recommendation_training_dataset.py

기존 사용자 행동 로그(logs.csv)로 추천 랭킹 학습용 weak-label JSONL을 만든다.
초기에는 챗봇 피드백이 부족하므로 click/view/bookmark/reservation 로그를
query별 relevance label로 사용해 가중치 튜닝과 Learning-to-Rank 실험을 시작한다.

사용법:
    python scripts/build_recommendation_training_dataset.py \
      --output data/recommendation_training_samples.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.chatbot.recommendation_engine import (  # noqa: E402
    _normalize_query,
    _propagate_queries_and_aggregate,
    recommendation_engine,
)


def _read_logs(path: Path, max_rows: int) -> pd.DataFrame:
    nrows = None if max_rows <= 0 else max_rows
    return pd.read_csv(path, encoding="utf-8-sig", nrows=nrows)


def _numeric(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if pd.isna(number):
        return 0.0
    return number


def _query_relevance(events: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    events = events.copy()
    events["query_key"] = events["search_query"].map(_normalize_query)
    events = events[events["query_key"] != ""]
    grouped = events.groupby(["query_key", "shop_id"], as_index=False)["weight"].sum()
    totals = grouped.groupby("query_key")["weight"].sum().sort_values(ascending=False)
    return grouped, totals.index.tolist()


def _normalise_relevance(rows: pd.DataFrame) -> dict[str, float]:
    raw = {
        str(row.shop_id): _numeric(row.weight)
        for row in rows.itertuples(index=False)
        if str(row.shop_id).strip()
    }
    if not raw:
        return {}
    max_rel = max(raw.values()) or 1.0
    return {shop_id: value / max_rel for shop_id, value in raw.items()}


def _build_sample(query: str, recommendation: dict[str, Any], label: float) -> dict[str, Any]:
    breakdown = recommendation.get("score_breakdown")
    if not isinstance(breakdown, dict):
        breakdown = {}
    contributions = recommendation.get("score_contributions")
    if not isinstance(contributions, dict):
        contributions = {}

    categories = recommendation.get("categories") or []
    menus = recommendation.get("menus") or []
    return {
        "query": query,
        "shop_id": str(recommendation.get("shop_id") or "").strip(),
        "label": round(label, 4),
        "source": "behavior_log",
        "features": {
            "rank": recommendation.get("rank"),
            "score": recommendation.get("score"),
            "score_before_adjustments": recommendation.get("score_before_adjustments"),
            "bm25": breakdown.get("bm25"),
            "intent": breakdown.get("intent"),
            "popularity": breakdown.get("popularity"),
            "personal": breakdown.get("personal"),
            "bm25_contribution": contributions.get("bm25"),
            "intent_contribution": contributions.get("intent"),
            "popularity_contribution": contributions.get("popularity"),
            "personal_contribution": contributions.get("personal"),
            "category_count": len(categories),
            "menu_count": len(menus),
        },
        "shop": {
            "shop_name": recommendation.get("shop_name"),
            "categories": categories,
            "menus": menus,
        },
    }


def _build_samples_for_query(
    query: str,
    relevance_map: dict[str, float],
    recommendations: list[dict[str, Any]],
    *,
    min_positive_per_query: int,
) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    seen_shop_ids: set[str] = set()

    for recommendation in recommendations:
        shop_id = str(recommendation.get("shop_id") or "").strip()
        if not shop_id or shop_id in seen_shop_ids:
            continue
        seen_shop_ids.add(shop_id)
        samples.append(_build_sample(query, recommendation, relevance_map.get(shop_id, 0.0)))

    positive_count = sum(1 for sample in samples if sample["label"] > 0)
    if positive_count < min_positive_per_query:
        return []
    return samples


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def build_recommendation_training_dataset(
    *,
    logs_path: Path,
    shops_path: str,
    cache_path: str,
    output_path: Path,
    max_rows: int,
    max_queries: int,
    candidate_k: int,
    min_positive_per_query: int,
) -> dict[str, Any]:
    if not logs_path.exists():
        raise FileNotFoundError(f"logs.csv 없음: {logs_path}")

    previous_env = {
        "SHOPS_CSV_PATH": os.environ.get("SHOPS_CSV_PATH"),
        "LOG_CACHE_PATH": os.environ.get("LOG_CACHE_PATH"),
    }
    os.environ["SHOPS_CSV_PATH"] = shops_path
    os.environ["LOG_CACHE_PATH"] = cache_path
    try:
        recommendation_engine.load(shops_path=shops_path, logs_path=str(logs_path))
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    logs_df = _read_logs(logs_path, max_rows)
    events = _propagate_queries_and_aggregate(logs_df)
    if events.empty:
        raise ValueError("학습 샘플을 만들 수 있는 행동 로그가 없습니다.")

    grouped, query_keys = _query_relevance(events)
    if max_queries > 0:
        query_keys = query_keys[:max_queries]

    samples: list[dict[str, Any]] = []
    included_queries = 0
    for query_key in query_keys:
        relevance_rows = grouped[grouped["query_key"] == query_key]
        relevance_map = _normalise_relevance(relevance_rows)
        recommendations = recommendation_engine.recommend(
            query_key,
            top_k=candidate_k,
            diversify=False,
        )
        query_samples = _build_samples_for_query(
            query_key,
            relevance_map,
            recommendations,
            min_positive_per_query=min_positive_per_query,
        )
        if query_samples:
            included_queries += 1
            samples.extend(query_samples)

    _write_jsonl(output_path, samples)

    positive = sum(1 for sample in samples if sample["label"] > 0)
    negative = len(samples) - positive
    return {
        "logs": str(logs_path),
        "shops": shops_path,
        "output": str(output_path),
        "max_rows": "all" if max_rows <= 0 else max_rows,
        "max_queries": "all" if max_queries <= 0 else max_queries,
        "candidate_k": candidate_k,
        "min_positive_per_query": min_positive_per_query,
        "queries_considered": len(query_keys),
        "queries_included": included_queries,
        "samples": len(samples),
        "positive": positive,
        "negative": negative,
        "positive_rate": round(positive / len(samples), 4) if samples else 0.0,
        "avg_samples_per_query": round(len(samples) / included_queries, 2) if included_queries else 0.0,
        "avg_positive_per_query": round(positive / included_queries, 2) if included_queries else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="행동 로그 기반 추천 랭킹 weak-label 학습셋 생성")
    parser.add_argument("--logs", default="data/logs.csv", help="logs.csv 경로")
    parser.add_argument("--shops", default="data/shops.csv", help="shops.csv 경로")
    parser.add_argument("--cache", default="data/log_cache.pkl", help="log_cache.pkl 경로")
    parser.add_argument("--output", default="data/recommendation_training_samples.jsonl", help="출력 JSONL 경로")
    parser.add_argument("--max-rows", type=int, default=500_000, help="사용할 로그 행 수. 0이면 전체")
    parser.add_argument("--max-queries", type=int, default=200, help="상위 query 수. 0이면 전체")
    parser.add_argument("--candidate-k", type=int, default=50, help="query별 추천 후보 수")
    parser.add_argument("--min-positive-per-query", type=int, default=1, help="query별 최소 positive 후보 수")
    args = parser.parse_args()

    try:
        summary = build_recommendation_training_dataset(
            logs_path=Path(args.logs),
            shops_path=args.shops,
            cache_path=args.cache,
            output_path=Path(args.output),
            max_rows=args.max_rows,
            max_queries=args.max_queries,
            candidate_k=args.candidate_k,
            min_positive_per_query=args.min_positive_per_query,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
