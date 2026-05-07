"""
routes/chatbot.py

식당 추천 챗봇 API 엔드포인트.

POST /chatbot/chat      — 챗봇 메시지 전송
POST /chatbot/chat/stream — 챗봇 메시지 전송(SSE)
POST /chatbot/reset     — 대화 기록 초기화
POST /chatbot/feedback  — 추천 피드백 기록
GET  /chatbot/profile   — 장기 메모리 프로필 조회
GET  /chatbot/status    — 엔진/챗봇 초기화 상태 확인
"""

import re
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from app.chatbot import chatbot_controller
from app.chatbot.chatbot_chain import chatbot_chain
from app.chatbot.intent_router import supported_features
from app.chatbot.personalization import personalization_store
from app.chatbot.recommendation_engine import recommendation_engine
from app.common.auth import get_user_id_from_request
from app.common.responses import ok

router = APIRouter(prefix="/chatbot", tags=["chatbot"])
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


class ChatRequest(BaseModel):
    message: str = Field(
        ..., min_length=1, max_length=500, description="사용자 메시지"
    )
    session_id: str | None = Field(
        None, max_length=128, description="세션 격리를 위한 고유 ID"
    )
    profile: dict[str, Any] | None = Field(
        None, description="클라이언트 LocalStorage에 저장된 개인 취향 프로필"
    )


class ResetRequest(BaseModel):
    session_id: str | None = Field(
        None, max_length=128, description="세션 격리를 위한 고유 ID"
    )


class FeedbackRequest(BaseModel):
    session_id: str | None = Field(
        None, max_length=128, description="세션 격리를 위한 고유 ID"
    )
    shop_id: str = Field(..., min_length=1, max_length=128, description="피드백 대상 매장 ID")
    action: str = Field(..., description="like | dislike | save")
    shop: dict[str, Any] | None = Field(
        None, description="피드백 대상 추천 카드 데이터"
    )


def _resolve_session_id(value: str | None) -> str:
    session_id = (value or "default").strip()
    if not SESSION_ID_RE.fullmatch(session_id):
        return "default"
    return session_id


def _resolve_memory_id(request: Request, session_id: str) -> str:
    user_id = get_user_id_from_request(request)
    return f"user:{user_id}" if user_id else session_id


@router.post("/chat")
def chat(payload: ChatRequest, request: Request):
    """
    식당 추천 챗봇에 메시지를 전송합니다.

    - 식당/지역 관련 질문 → 추천 모델 기반 응답
    - 비관련 질문 → 정중히 거절
    """
    session_id = _resolve_session_id(payload.session_id)
    return chatbot_controller.chat(
        user_message=payload.message,
        session_id=session_id,
        profile=payload.profile,
        memory_id=_resolve_memory_id(request, session_id),
    )


@router.post("/chat/stream")
def chat_stream(payload: ChatRequest, request: Request):
    """식당 추천 챗봇 응답을 SSE 형태로 전송합니다."""
    session_id = _resolve_session_id(payload.session_id)
    return chatbot_controller.chat_stream(
        user_message=payload.message,
        session_id=session_id,
        profile=payload.profile,
        memory_id=_resolve_memory_id(request, session_id),
    )


@router.post("/reset")
def reset_session(request: Request, payload: ResetRequest | None = None):
    """대화 기록(메모리)을 초기화합니다."""
    session_id = _resolve_session_id(payload.session_id if payload else None)
    return chatbot_controller.reset_session(
        session_id,
        memory_id=_resolve_memory_id(request, session_id),
    )


@router.post("/feedback")
def record_feedback(payload: FeedbackRequest, request: Request):
    """추천 카드에 대한 좋아요/별로/저장 피드백을 기록합니다."""
    session_id = _resolve_session_id(payload.session_id)
    return chatbot_controller.record_feedback(
        session_id=session_id,
        shop_id=payload.shop_id,
        action=payload.action,
        shop=payload.shop,
        memory_id=_resolve_memory_id(request, session_id),
    )


@router.get("/profile")
def get_profile(request: Request, session_id: str | None = Query(None, max_length=128)):
    """세션에 저장된 챗봇 장기 취향 프로필을 반환합니다."""
    resolved_session_id = _resolve_session_id(session_id)
    return chatbot_controller.get_profile(
        resolved_session_id,
        memory_id=_resolve_memory_id(request, resolved_session_id),
    )


@router.get("/status")
def get_status():
    """
    추천 엔진과 챗봇 초기화 상태를 반환합니다.

    LLM provider: gemini | ollama | mock
    """
    return ok(
        message="status_ok",
        data={
            "recommendation_engine": {
                "ready": recommendation_engine.is_ready(),
                "shop_count": recommendation_engine.shop_count,
                "rank_weight_source": recommendation_engine.rank_weight_source,
            },
            "chatbot": {
                "provider": chatbot_chain._provider,
                "initialized": chatbot_chain._initialized,
                "personalization": personalization_store.stats(),
                "supported_features": supported_features(),
            },
        },
    )
