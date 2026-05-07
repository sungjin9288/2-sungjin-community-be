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

import asyncio
import json
import logging
from typing import Any

from fastapi.responses import JSONResponse, StreamingResponse

from app.chatbot.chatbot_chain import chatbot_chain
from app.chatbot.learning_log import learning_log_writer
from app.chatbot.personalization import (
    clarification_suggestions,
    clarification_question,
    extract_preferences,
    is_food_related,
    personalization_store,
    profile_summary,
    should_ask_clarification,
)
from app.chatbot.recommendation_engine import recommendation_engine
from app.common.exceptions import MissingRequiredFieldsError
from app.common.responses import ok

logger = logging.getLogger(__name__)

RECOMMEND_TOP_K = 5


def _record_chat_learning_event(
    *,
    session_id: str,
    user_message: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    learning_log_writer.record_chat(
        session_id=session_id,
        message=user_message,
        reply=str(payload.get("reply") or ""),
        recommended=payload.get("recommended") or [],
        profile=payload.get("profile") or {},
        profile_summary=str(payload.get("profile_summary") or ""),
        clarification=bool(payload.get("clarification")),
        next_questions=payload.get("next_questions") or [],
    )
    return payload


def _chat_payload(
    user_message: str,
    session_id: str = "default",
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    사용자 메시지를 받아 챗봇 응답 payload를 만든다.
    """
    user_message = (user_message or "").strip()
    if not user_message:
        raise MissingRequiredFieldsError("메시지를 입력해주세요.")

    logger.info("챗봇 요청 (session=%s): %r", session_id, user_message[:80])

    if not is_food_related(user_message):
        stored_profile = personalization_store.get_profile(session_id)
        summary = profile_summary(stored_profile)
        reply = chatbot_chain.chat(
            user_message=user_message,
            recommended_shops=[],
            session_id=session_id,
            preference_summary=summary,
        )
        return _record_chat_learning_event(
            session_id=session_id,
            user_message=user_message,
            payload={
                "reply": reply,
                "recommended": [],
                "profile": stored_profile,
                "profile_summary": summary,
                "clarification": False,
                "next_questions": [
                    "강남 데이트 파스타 추천해줘",
                    "강남 회식 고기집 추천해줘",
                    "라면 맛집 추천해줘",
                ],
            },
        )

    current_profile = extract_preferences(user_message)
    merged_profile = personalization_store.update_from_message(
        session_id=session_id,
        message=user_message,
        client_profile=profile,
    )
    summary = profile_summary(merged_profile)

    if should_ask_clarification(
        user_message,
        merged_profile,
        current_profile=current_profile,
    ):
        question = clarification_question(
            merged_profile,
            message=user_message,
            current_profile=current_profile,
        )
        return _record_chat_learning_event(
            session_id=session_id,
            user_message=user_message,
            payload={
                "reply": question,
                "recommended": [],
                "profile": merged_profile,
                "profile_summary": summary,
                "clarification": True,
                "next_questions": clarification_suggestions(
                    merged_profile,
                    message=user_message,
                    current_profile=current_profile,
                ),
            },
        )

    # 추천 엔진 실행
    recommended: list[dict] = []
    if recommendation_engine.is_ready():
        try:
            recommended = recommendation_engine.recommend(
                user_message,
                top_k=RECOMMEND_TOP_K,
                profile=merged_profile,
                feedback=personalization_store.get_feedback(session_id),
                diversify=True,
            )
        except Exception as exc:
            logger.error("추천 엔진 오류: %s", exc)

    # LLM 응답 생성
    try:
        reply = chatbot_chain.chat(
            user_message=user_message,
            recommended_shops=recommended,
            session_id=session_id,
            preference_summary=summary,
        )
    except Exception as exc:
        logger.error("챗봇 응답 생성 오류: %s", exc)
        reply = "죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."

    logger.info("챗봇 응답 완료 (추천 %d개)", len(recommended))

    return _record_chat_learning_event(
        session_id=session_id,
        user_message=user_message,
        payload={
            "reply": reply,
            "recommended": recommended,
            "profile": merged_profile,
            "profile_summary": summary,
            "clarification": False,
            "next_questions": [
                "더 저렴한 곳으로 다시 추천해줘",
                "비슷하지만 분위기 좋은 곳으로 바꿔줘",
                "저장한 취향 기준으로 다시 골라줘",
            ],
        },
    )


def chat(
    user_message: str,
    session_id: str = "default",
    profile: dict[str, Any] | None = None,
) -> JSONResponse:
    """
    사용자 메시지를 받아 챗봇 응답과 추천 식당 목록을 반환한다.
    """
    return ok(
        message="chat_success",
        data=_chat_payload(user_message, session_id, profile),
    )


def reset_session(session_id: str = "default") -> JSONResponse:
    """대화 기록 초기화."""
    chatbot_chain.reset_memory(session_id)
    personalization_store.reset(session_id)
    return ok(message="session_reset", data=None)


def get_profile(session_id: str = "default") -> JSONResponse:
    profile = personalization_store.get_profile(session_id)
    return ok(
        message="profile_loaded",
        data={
            "profile": profile,
            "profile_summary": profile_summary(profile),
            "storage": personalization_store.backend,
        },
    )


def record_feedback(
    session_id: str,
    shop_id: str,
    action: str,
    shop: dict[str, Any] | None = None,
) -> JSONResponse:
    result = personalization_store.record_feedback(session_id, shop_id, action, shop)
    learning_log_writer.record_feedback(
        session_id=session_id,
        shop_id=shop_id,
        action=action,
        shop=shop,
        profile=result.get("profile") or {},
        profile_summary=profile_summary(result.get("profile") or {}),
        feedback_counts=result.get("feedback_counts") or {},
    )
    return ok(message="feedback_recorded", data=result)


def chat_stream(
    user_message: str,
    session_id: str = "default",
    profile: dict[str, Any] | None = None,
) -> StreamingResponse:
    async def event_generator():
        payload = _chat_payload(user_message, session_id, profile)
        reply = str(payload.get("reply") or "")
        for token in reply.split(" "):
            if token:
                yield f"event: chunk\ndata: {json.dumps(token + ' ', ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.015)
        yield f"event: done\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
