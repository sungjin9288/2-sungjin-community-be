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
from app.chatbot.intent_router import classify_chat_intent
from app.chatbot.learning_log import learning_log_writer
from app.chatbot.personalization import (
    clarification_suggestions,
    clarification_question,
    extract_preferences,
    merge_profiles,
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
        intent=payload.get("intent") or {},
    )
    return payload


def _starter_questions() -> list[str]:
    return [
        "강남 데이트 파스타 추천해줘",
        "강남 회식 고기집 추천해줘",
        "라면 맛집 추천해줘",
    ]


def _unsupported_community_payload(
    *,
    route: dict[str, Any],
    profile: dict[str, Any],
    summary: str,
) -> dict[str, Any]:
    return {
        "reply": (
            "커뮤니티 글 검색, 북마크, 알림 요약은 챗봇 기능으로 분리해 둘 수 있지만 "
            "아직 API 도구 연결 전입니다. 현재 바로 사용할 수 있는 기능은 행동 로그 기반 식당 추천입니다."
        ),
        "recommended": [],
        "profile": profile,
        "profile_summary": summary,
        "clarification": False,
        "next_questions": _starter_questions(),
        "intent": route,
    }


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

    stored_profile = personalization_store.get_profile(session_id)
    route_profile = merge_profiles(stored_profile, profile)
    route = classify_chat_intent(user_message, route_profile)
    route_payload = route.to_dict()

    logger.info(
        "챗봇 요청 (session=%s, intent=%s): %r",
        session_id,
        route.name,
        user_message[:80],
    )

    if route.name == "preference_profile":
        summary = profile_summary(route_profile)
        reply = (
            f"현재 기억한 취향은 {summary}입니다."
            if summary != "아직 저장된 취향이 없습니다."
            else "아직 저장된 취향이 없습니다. 지역, 메뉴, 상황을 말해주면 취향 프로필에 반영할게요."
        )
        return _record_chat_learning_event(
            session_id=session_id,
            user_message=user_message,
            payload={
                "reply": reply,
                "recommended": [],
                "profile": route_profile,
                "profile_summary": summary,
                "clarification": False,
                "next_questions": _starter_questions(),
                "intent": route_payload,
            },
        )

    if route.name == "community_assistant":
        summary = profile_summary(route_profile)
        return _record_chat_learning_event(
            session_id=session_id,
            user_message=user_message,
            payload=_unsupported_community_payload(
                route=route_payload,
                profile=route_profile,
                summary=summary,
            ),
        )

    if route.name != "restaurant_recommendation":
        summary = profile_summary(route_profile)
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
                "profile": route_profile,
                "profile_summary": summary,
                "clarification": False,
                "next_questions": _starter_questions(),
                "intent": route_payload,
            },
        )

    current_profile = extract_preferences(user_message)
    merged_profile = personalization_store.update_from_message(
        session_id=session_id,
        message=user_message,
        client_profile=profile,
    )
    summary = profile_summary(merged_profile)
    recommend_query = user_message
    if route.reason == "saved_profile_recommendation":
        recommend_query = f"{user_message} {summary}"

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
                "intent": route_payload,
            },
        )

    # 추천 엔진 실행
    recommended: list[dict] = []
    if recommendation_engine.is_ready():
        try:
            recommended = recommendation_engine.recommend(
                recommend_query,
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
            user_message=recommend_query,
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
            "intent": route_payload,
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
