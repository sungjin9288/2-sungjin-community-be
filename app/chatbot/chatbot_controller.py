"""
chatbot_controller.py

식당 추천 챗봇 오케스트레이션.

흐름:
  1. 사용자 메시지 수신
  2. RecommendationEngine → 식당 후보 검색
  3. ChatbotChain → 자연어 응답 생성
  4. 응답 + 추천 식당 목록 반환
"""

from __future__ import annotations

import logging

from fastapi.responses import JSONResponse

from app.chatbot.chatbot_chain import chatbot_chain
from app.chatbot.recommendation_engine import recommendation_engine
from app.common.exceptions import MissingRequiredFieldsError
from app.common.responses import ok

logger = logging.getLogger(__name__)

RECOMMEND_TOP_K = 5


def chat(user_message: str) -> JSONResponse:
    """
    사용자 메시지를 받아 챗봇 응답과 추천 식당 목록을 반환한다.
    """
    user_message = (user_message or "").strip()
    if not user_message:
        raise MissingRequiredFieldsError("메시지를 입력해주세요.")

    logger.info("챗봇 요청: %r", user_message[:80])

    # 추천 엔진 실행
    recommended: list[dict] = []
    if recommendation_engine.is_ready():
        try:
            recommended = recommendation_engine.recommend(
                user_message, top_k=RECOMMEND_TOP_K
            )
        except Exception as exc:
            logger.error("추천 엔진 오류: %s", exc)

    # LLM 응답 생성
    try:
        reply = chatbot_chain.chat(
            user_message=user_message,
            recommended_shops=recommended,
        )
    except Exception as exc:
        logger.error("챗봇 응답 생성 오류: %s", exc)
        reply = "죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."

    logger.info("챗봇 응답 완료 (추천 %d개)", len(recommended))

    return ok(
        message="chat_success",
        data={
            "reply": reply,
            "recommended": recommended,
        },
    )


def reset_session() -> JSONResponse:
    """대화 기록 초기화."""
    chatbot_chain.reset_memory()
    return ok(message="session_reset", data=None)
