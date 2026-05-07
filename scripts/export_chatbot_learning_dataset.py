"""
scripts/export_chatbot_learning_dataset.py

챗봇 학습 로그(JSONL)를 추천 랭킹 학습용 샘플(JSONL)로 변환한다.

사용법:
    python scripts/export_chatbot_learning_dataset.py
    python scripts/export_chatbot_learning_dataset.py \
        --input data/chatbot_learning_logs.jsonl \
        --output data/chatbot_training_samples.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ACTION_LABELS = {
    "like": 1.0,
    "save": 1.0,
    "dislike": 0.0,
}


def _read_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not path.exists():
        return events

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
    return events


def _find_recommendation(chat_event: dict[str, Any] | None, shop_id: str) -> dict[str, Any]:
    if not chat_event:
        return {}
    recommendations = chat_event.get("recommendations") or []
    for recommendation in recommendations:
        if str(recommendation.get("shop_id") or "") == shop_id:
            return recommendation
    return {}


def _build_features(recommendation: dict[str, Any], feedback_shop: dict[str, Any]) -> dict[str, Any]:
    shop = recommendation or feedback_shop
    breakdown = shop.get("score_breakdown") or {}
    contributions = shop.get("score_contributions") or {}
    return {
        "rank": shop.get("rank"),
        "score": shop.get("score"),
        "score_before_adjustments": shop.get("score_before_adjustments"),
        "bm25": breakdown.get("bm25"),
        "intent": breakdown.get("intent"),
        "popularity": breakdown.get("popularity"),
        "personal": breakdown.get("personal"),
        "bm25_contribution": contributions.get("bm25"),
        "intent_contribution": contributions.get("intent"),
        "popularity_contribution": contributions.get("popularity"),
        "personal_contribution": contributions.get("personal"),
        "category_count": len(shop.get("categories") or []),
        "menu_count": len(shop.get("menus") or []),
    }


def export_training_dataset(input_path: Path, output_path: Path) -> dict[str, int]:
    events = _read_events(input_path)
    session_chats: dict[str, list[dict[str, Any]]] = {}
    samples: list[dict[str, Any]] = []

    for event in events:
        event_type = event.get("event_type")
        session_id = str(event.get("session_id") or "default")
        if event_type == "chat":
            session_chats.setdefault(session_id, []).append(event)
            continue

        if event_type != "feedback":
            continue

        action = str(event.get("action") or "").strip()
        if action not in ACTION_LABELS:
            continue

        shop_id = str(event.get("shop_id") or "").strip()
        if not shop_id:
            continue

        matched_chat = None
        recommendation = {}
        for chat_event in reversed(session_chats.get(session_id, [])):
            recommendation = _find_recommendation(chat_event, shop_id)
            if recommendation:
                matched_chat = chat_event
                break

        feedback_shop = event.get("shop") if isinstance(event.get("shop"), dict) else {}
        sample = {
            "session_id": session_id,
            "query": (matched_chat or {}).get("message") or "",
            "shop_id": shop_id,
            "label": ACTION_LABELS[action],
            "action": action,
            "profile": event.get("profile") or {},
            "features": _build_features(recommendation, feedback_shop),
            "shop": {
                "shop_name": (recommendation or feedback_shop).get("shop_name"),
                "categories": (recommendation or feedback_shop).get("categories") or [],
                "menus": (recommendation or feedback_shop).get("menus") or [],
            },
        }
        samples.append(sample)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False, separators=(",", ":")) + "\n")

    return {
        "events": len(events),
        "samples": len(samples),
        "positive": sum(1 for sample in samples if sample["label"] > 0),
        "negative": sum(1 for sample in samples if sample["label"] <= 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="챗봇 학습 로그를 랭킹 학습 샘플로 변환")
    parser.add_argument("--input", default="data/chatbot_learning_logs.jsonl", help="입력 학습 로그 JSONL")
    parser.add_argument("--output", default="data/chatbot_training_samples.jsonl", help="출력 학습 샘플 JSONL")
    args = parser.parse_args()

    summary = export_training_dataset(Path(args.input), Path(args.output))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
