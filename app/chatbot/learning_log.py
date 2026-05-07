"""
chatbot learning log writer.

챗봇 추천 결과와 카드 피드백을 JSONL로 남겨 이후 랭킹/개인화 모델 학습
데이터로 재사용할 수 있게 한다. 런타임 API 응답은 로그 저장 실패에
영향받지 않는다.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_LEARNING_LOG_PATH = "data/chatbot_learning_logs.jsonl"
DISABLED_VALUES = {"0", "false", "no", "off"}


def _learning_log_enabled() -> bool:
    return os.getenv("CHATBOT_LEARNING_LOG_ENABLED", "1").strip().lower() not in DISABLED_VALUES


def _learning_log_path() -> Path:
    return Path(os.getenv("CHATBOT_LEARNING_LOG_PATH", DEFAULT_LEARNING_LOG_PATH))


def _compact_shop(shop: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(shop, dict):
        return {}
    return {
        "shop_id": shop.get("shop_id"),
        "shop_name": shop.get("shop_name"),
        "categories": shop.get("categories") or [],
        "menus": (shop.get("menus") or [])[:5],
        "score": shop.get("score"),
        "score_breakdown": shop.get("score_breakdown") or {},
        "reasons": shop.get("reasons") or [],
        "ranking_formula": shop.get("ranking_formula"),
        "rank": shop.get("rank"),
    }


class LearningLogWriter:
    """Append-only JSONL writer for recommendation training/evaluation events."""

    def write(self, event_type: str, payload: dict[str, Any]) -> None:
        if not _learning_log_enabled():
            return

        event = {
            "event_type": event_type,
            "created_at_ms": int(time.time() * 1000),
            **payload,
        }
        path = _learning_log_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
        except Exception as exc:
            logger.warning("챗봇 학습 로그 저장 실패: %s", exc)

    def record_chat(
        self,
        *,
        session_id: str,
        message: str,
        reply: str,
        recommended: list[dict[str, Any]],
        profile: dict[str, Any],
        profile_summary: str,
        clarification: bool,
        next_questions: list[str],
        intent: dict[str, Any] | None = None,
    ) -> None:
        self.write(
            "chat",
            {
                "session_id": session_id,
                "message": message,
                "reply": reply,
                "intent": intent or {},
                "profile": profile,
                "profile_summary": profile_summary,
                "clarification": clarification,
                "next_questions": next_questions,
                "recommendations": [
                    _compact_shop(shop)
                    for shop in recommended
                    if isinstance(shop, dict)
                ],
            },
        )

    def record_feedback(
        self,
        *,
        session_id: str,
        shop_id: str,
        action: str,
        shop: dict[str, Any] | None,
        profile: dict[str, Any],
        profile_summary: str,
        feedback_counts: dict[str, int],
    ) -> None:
        self.write(
            "feedback",
            {
                "session_id": session_id,
                "shop_id": shop_id,
                "action": action,
                "shop": _compact_shop(shop),
                "profile": profile,
                "profile_summary": profile_summary,
                "feedback_counts": feedback_counts,
            },
        )


learning_log_writer = LearningLogWriter()
