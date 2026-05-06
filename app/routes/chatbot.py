"""
routes/chatbot.py

식당 추천 챗봇 API 엔드포인트.

POST /chatbot/chat      — 챗봇 메시지 전송
POST /chatbot/reset     — 대화 기록 초기화
GET  /chatbot/status    — 엔진/챗봇 초기화 상태 확인
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.chatbot import chatbot_controller
from app.chatbot.chatbot_chain import chatbot_chain
from app.chatbot.recommendation_engine import recommendation_engine
from app.common.responses import ok

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


class ChatRequest(BaseModel):
    message: str = Field(
        ..., min_length=1, max_length=500, description="사용자 메시지"
    )


@router.post("/chat")
def chat(payload: ChatRequest):
    """
    식당 추천 챗봇에 메시지를 전송합니다.

    - 식당/지역 관련 질문 → 추천 모델 기반 응답
    - 비관련 질문 → 정중히 거절
    """
    return chatbot_controller.chat(user_message=payload.message)


@router.post("/reset")
def reset_session():
    """대화 기록(메모리)을 초기화합니다."""
    return chatbot_controller.reset_session()


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
            },
            "chatbot": {
                "provider": chatbot_chain._provider,
                "initialized": chatbot_chain._initialized,
            },
        },
    )
